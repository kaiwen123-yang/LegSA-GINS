"""Resumable P-13 orchestration around the unchanged frozen evaluator.

Completed run/version rows are immutable. Every result is persisted before the
next scheduling decision; the six registered first-batch probes are formal
evaluations and are never repeated for resource measurement.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
from pathlib import Path
import re

from ..clean5_degradation.common import resolve, write_json
from ..clean6_canonical_v2.evaluation import one_evaluation
from ..clean6_canonical_v2.io_recovery import ScientificStop, check_science_terminals
from ..clean6_canonical_v2.resources import choose_evaluator_workers
from ..clean6_canonical_v2.storage import append_json, machine_state
from ..manifest import sha256_file

VERSIONS = ('v3', 'v2')
DATASETS = ('BY2', 'BY2H', 'BY2O')
ALGORITHM_FAILURE = 'ALGORITHM_FAILURE_ALL_YAW_REJECTED'
PERMITTED = {'COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE'}


def _safe_id(value):
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', value) or value in ('.', '..'):
        raise ValueError('Unsafe evaluator run identity')
    return value


def _key(record, version):
    return _safe_id(record['run_id']), version


def _payload_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def _numeric_nonfinite(value):
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_numeric_nonfinite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_numeric_nonfinite(v) for v in value)
    return False


def _scientific_gate(record, row):
    check_science_terminals([record], [row])
    if (row.get('evaluation_status') not in PERMITTED or _numeric_nonfinite(row)
            or row.get('finite_output') is False):
        raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE',
                             'Evaluator terminal failed: '+str(row.get('run_id'))+' '+str(row.get('evaluator_version')))
    if row['evaluation_status'] == 'NOT_RUN_ALGORITHM_FAILURE' and record['terminal_status'] != ALGORITHM_FAILURE:
        raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE', 'Invalid algorithm-failure evaluator skip')
    if row['evaluation_status'] == 'COMPLETED' and record['terminal_status'] != 'COMPLETED':
        raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE', 'Evaluator completed for unsuccessful native run')


def _validate_identity(record, version, row, contract):
    if _key(record, version) != (str(row.get('run_id')), row.get('evaluator_version')):
        raise ValueError('Existing evaluator row identity mismatch')
    for key in ('dataset_id', 'case_id'):
        if row.get(key) is not None and record.get(key) is not None and row[key] != record[key]:
            raise ValueError('Existing evaluator row '+key+' mismatch')
    if row.get('evaluator_sha256') not in (None, contract['evaluation']['evaluator']['sha256']):
        raise ValueError('Existing row used a different evaluator identity')
    if row.get('native_nav_sha256') is not None and record.get('nav_sha256') is not None:
        if row['native_nav_sha256'] != record['nav_sha256']:
            raise ValueError('Existing evaluator row refers to a different native NAV')


def _terminal_path(output, record, version):
    return Path(output)/'EVALUATION_TERMINALS'/version/(_safe_id(record['run_id'])+'.json')


def _original_result(scratch, record, version):
    return Path(scratch)/'12_OFFLINE_EVALUATION'/version/_safe_id(record['run_id'])/'EVALUATION_RESULT.json'


def _metadata(record, row):
    """Carry P-13 provenance outside the unchanged evaluator's numeric result."""
    row = dict(row)
    for key in ('data_mode', 'synthetic_data_used', 'semisynthetic_data_used',
                'controlled_degradation_applied', 'sensor_model_group_hash', 'domain'):
        if key in record:
            row[key] = record[key]
    return row


def _persist(output, record, version, row, *, recovered=False):
    """Persist a terminal before raising any scientific failure or aggregating."""
    path = _terminal_path(output, record, version)
    # Nonfinite output cannot be serialized as a valid scientific result. Keep
    # the original diagnostic representation alongside an explicit failure row.
    if _numeric_nonfinite(row):
        diagnostic = repr(row)
        row = {'run_id': record['run_id'], 'evaluator_version': version,
               'dataset_id': record.get('dataset_id'), 'case_id': record.get('case_id'),
               'evaluation_status': 'FAILED_EVALUATOR', 'finite_output': False,
               'failure_type': 'NonfiniteResult', 'failure_message': 'nonfinite evaluator terminal',
               'original_result_repr': diagnostic, 'evaluation_invoked': row.get('evaluation_invoked', True)}
        row = _metadata(record, row)
    envelope = {'schema_version': 'clean6.sensor_v21.evaluation_terminal.v1',
                'row': row, 'row_sha256': _payload_hash(row), 'recovered_existing_result': recovered}
    if path.exists():
        existing = json.loads(path.read_text())
        if existing['row_sha256'] != envelope['row_sha256']:
            raise ValueError('Immutable evaluator terminal already exists with different contents')
    else:
        write_json(path, envelope)
    return row


def _existing(output, scratch, record, version, contract):
    path = _terminal_path(output, record, version)
    if path.exists():
        data = json.loads(path.read_text())
        row = data['row']
        if data['row_sha256'] != _payload_hash(row):
            raise ValueError('Evaluator terminal hash differs')
    else:
        original = _original_result(scratch, record, version)
        if not original.is_file():
            return None
        row = _metadata(record, json.loads(original.read_text()))
        _validate_identity(record, version, row, contract)
        row = _persist(output, record, version, row, recovered=True)
    _validate_identity(record, version, row, contract)
    _scientific_gate(record, row)
    return row


def _call(record, version, contract, reg, scratch, commit):
    root = _original_result(scratch, record, version).parent
    if root.exists():
        # A missing terminal in an existing exclusive invocation directory is
        # unresolved evidence, not permission to invoke the evaluator again.
        raise ValueError('Existing evaluator invocation has no terminal; preserve for bookkeeping recovery: '+str(root))
    try:
        return _metadata(record, one_evaluation(record, version, contract, reg, scratch, commit))
    except Exception as error:
        return {'run_id': record['run_id'], 'evaluator_version': version,
                'dataset_id': record.get('dataset_id'), 'case_id': record.get('case_id'),
                'evaluation_status': 'FAILED_EVALUATOR', 'evaluation_invoked': True,
                'failure_type': type(error).__name__, 'failure_message': str(error),
                'technical_failure': True, 'finite_output': False}


def _rss(row):
    value = row.get('evaluator_peak_rss_bytes')
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _note(output, operation, reason, **details):
    append_json(Path(output)/'EVALUATOR_BOOKKEEPING.jsonl',
                {'operation': operation, 'reason': reason, **details})


def _workers(state, solver_peak, rss_peak, output):
    try:
        return choose_evaluator_workers(state['memory_available_bytes'], solver_peak, rss_peak, state['nproc'])
    except ValueError as error:
        # Human P-13 adjudication inherits P-09c's validation/resource fallback;
        # an unavailable measurement is recorded, never replaced by zero RSS.
        _note(output, 'reduce_evaluator_pool', str(error), workers=1,
              evaluator_rss_status='AVAILABLE' if rss_peak else 'UNAVAILABLE')
        return 1


def _probe_spec(records):
    probes = []
    for dataset in DATASETS:
        candidates = [r for r in records if r.get('dataset_id') == dataset and r['terminal_status'] == 'COMPLETED']
        if not candidates:
            raise ValueError('First evaluator batch requires an existing completed native run for '+dataset)
        probes.extend((candidates[0], version) for version in VERSIONS)
    return probes


def evaluate_batch(records, contract, reg, scratch_batch, code_commit, output, solver_peak, *, io_context=None):
    """Drop-in P-09c signature returning (all rows, resource report).

    Paths: output/EVALUATION_TERMINALS/{version}/{run_id}.json stores sealed row
    envelopes immediately. stage/PILOT_GATE.json stores six first-batch probe
    identities/RSS. On recovery the wrapper also adopts already persisted frozen
    EVALUATION_RESULT.json files before considering a new invocation.
    """
    records, output, scratch = list(records), Path(output), Path(scratch_batch)
    output.mkdir(parents=True, exist_ok=True)
    check_science_terminals(records)
    if any(r['terminal_status'] not in ('COMPLETED', ALGORITHM_FAILURE) for r in records):
        raise ScientificStop('NATIVE_UNREGISTERED_FAILURE', 'Unexpected native terminal before evaluation')
    tasks = [(r, v) for r in records for v in VERSIONS]
    keys = [_key(r, v) for r, v in tasks]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate run/version evaluation task')
    completed, recovered = {}, 0
    for record, version in tasks:
        row = _existing(output, scratch, record, version, contract)
        if row is not None:
            completed[_key(record, version)] = row
            recovered += 1
    initial = machine_state()
    stage = resolve(contract['stage_root'], reg)
    pilot_path = stage/'PILOT_GATE.json'
    rss_peak = max([0]+[_rss(r) for r in completed.values()])
    probe_keys, plans = [], []
    if pilot_path.is_file():
        pilot = json.loads(pilot_path.read_text())
        if pilot.get('status') != 'PASS' or pilot.get('completed_probe_count') != 6:
            raise ValueError('Existing P13 evaluator pilot gate is incomplete')
        if pilot.get('evaluator_sha256') != contract['evaluation']['evaluator']['sha256']:
            raise ValueError('Existing evaluator pilot used a different frozen evaluator')
        rss_peak = max(rss_peak, pilot.get('evaluator_peak_rss_bytes') or 0)
    else:
        probes = _probe_spec(records)
        measurements = []
        for record, version in probes:
            key = _key(record, version)
            probe_keys.append(key)
            if key not in completed:
                if rss_peak:
                    _workers(machine_state(), solver_peak, rss_peak, output)
                row = _call(record, version, contract, reg, scratch, code_commit)
                row = _persist(output, record, version, row)
                _validate_identity(record, version, row, contract)
                _scientific_gate(record, row)
                completed[key] = row
            row = completed[key]
            rss_peak = max(rss_peak, _rss(row))
            path = _terminal_path(output, record, version)
            measurements.append({'run_id': key[0], 'dataset_id': record['dataset_id'], 'evaluator_version': version,
                                 'evaluator_peak_rss_bytes': _rss(row) or None,
                                 'terminal_path': str(path), 'terminal_sha256': sha256_file(path)})
            print('P13_EVALUATOR_PROBE', key[0], version, row.get('evaluation_runtime_seconds'), _rss(row) or 'UNAVAILABLE', flush=True)
        measured_count = sum(m['evaluator_peak_rss_bytes'] is not None for m in measurements)
        pilot = {'schema_version': 'clean6.sensor_v21.evaluator_pilot.v1', 'status': 'PASS',
                 'completed_probe_count': len(measurements), 'probes': measurements,
                 'evaluator_peak_rss_bytes': rss_peak or None,
                 'measured_probe_count': measured_count,
                 'measurement_status': 'AVAILABLE' if measured_count == 6 else 'PARTIALLY_AVAILABLE' if measured_count else 'UNAVAILABLE',
                 'evaluator_sha256': contract['evaluation']['evaluator']['sha256'],
                 'solver_peak_bytes': solver_peak, 'code_commit': code_commit,
                 'probe_policy': 'first completed native run per BY2/BY2H/BY2O, serial v3 then v2; formal rows reused',
                 'memory_fraction': .75, 'safety_factor': 1.25, 'maximum_workers': 22,
                 'evaluator_repeat_calls': 0}
        write_json(pilot_path, pilot)
    pending = [(r, v) for r, v in tasks if _key(r, v) not in completed]
    while pending:
        state = machine_state()
        count = _workers(state, solver_peak, rss_peak, output)
        wave, pending = pending[:count], pending[count:]
        plan = {'wave': len(plans)+1, 'workers': count, 'task_count': len(wave),
                'tasks': [{'run_id': r['run_id'], 'evaluator_version': v} for r, v in wave],
                'available_memory_bytes': state['memory_available_bytes'], 'solver_peak_bytes': solver_peak,
                'measured_evaluator_peak_rss_bytes': rss_peak or None,
                'reserved_peak_bytes': solver_peak+count*rss_peak*1.25 if rss_peak else None,
                'memory_budget_bytes': state['memory_available_bytes']*.75}
        plans.append(plan)
        append_json(output/'EVALUATOR_POOL_LEDGER.jsonl', plan)
        failures = []
        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = {pool.submit(_call, r, v, contract, reg, scratch, code_commit): (r, v) for r, v in wave}
            for future in as_completed(futures):
                record, version = futures[future]
                try:
                    row = future.result()
                    row = _persist(output, record, version, row)
                    completed[_key(record, version)] = row
                    rss_peak = max(rss_peak, _rss(row))
                    _validate_identity(record, version, row, contract)
                    _scientific_gate(record, row)
                except Exception as error:
                    failures.append(error)
        # All launched tasks have terminal evidence before the stop propagates.
        if failures:
            scientific = next((e for e in failures if isinstance(e, ScientificStop)), None)
            raise scientific or failures[0]
        if rss_peak and solver_peak+count*rss_peak*1.25 > plan['memory_budget_bytes']:
            _note(output, 'reduce_next_evaluator_wave', 'Measured RSS exceeds the previous wave estimate',
                  previous_workers=count, measured_evaluator_peak_rss_bytes=rss_peak)
        print('P13_EVALUATION_WAVE', len(plans), 'COMPLETE', len(completed), 'POOL', count, flush=True)
    ordered = [completed[key] for key in keys]
    report = {'initial_machine': initial, 'solver_peak_bytes': solver_peak,
              'evaluator_peak_rss_bytes': rss_peak or None, 'wave_plans': plans,
              'evaluator_pool_sizes': sorted({p['workers'] for p in plans}),
              'prior_terminal_rows_recovered': recovered, 'new_terminal_rows': len(ordered)-recovered,
              'evaluator_repeat_calls': 0, 'pilot_gate': str(pilot_path), 'pilot_gate_sha256': sha256_file(pilot_path)}
    return ordered, report
