"""Frozen P-09c batches: providers, solves, seals, evaluation, archive, cleanup."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

from ..clean5_degradation.common import (FLAGS, registry, pinned, resolve, resolved_pins,
                                        write_json, read_csv)
from ..clean5_degradation.runtime import checkpoint
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .contract import load_contract, selection, verify_preregistration, STAGE_NAME
from .runtime import run_one, profile_template, NUMERICAL_FILES
from .storage import (append_json, inventory, retain_run, cleanup_exact,
                      ResourceMonitor, machine_state)
from .resources import solver_workers, choose_evaluator_workers


def now():
    return datetime.now(timezone.utc).isoformat()


def restart_root(stage, contract):
    return stage/'RESTARTS'/contract['restart_authorization']['restart_id']


def active_freeze_path(stage, contract):
    amended = restart_root(stage, contract)/'CONTINUATION_FREEZE.json'
    return amended if amended.exists() else stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json'


def freeze_sources(code_root):
    """Record maintained imports and their tracked bytes at execution freeze."""
    paths = subprocess.check_output(['git', 'ls-files', '-z', 'src/legsa_gins/paper_rebuild',
        'src/legsa_gins/input_generation', 'scripts/paper_rebuild', 'configs/paper_rebuild'], cwd=code_root).decode().split('\0')
    return {p: sha256_file(code_root/p) for p in paths if p.endswith(('.py', '.yaml', '.json'))}


def validate_freeze(freeze, contract_path, reg):
    if sha256_file(contract_path) != freeze['contract_hash']:
        raise ValueError('Contract changed after execution freeze')
    for relative, digest in freeze['source_sha256'].items():
        if sha256_file(reg.code_root/relative) != digest:
            raise ValueError('Frozen source changed: '+relative)


def sequence_bundle(contract, reg, stage, dataset, code_commit):
    """Byte-copy the frozen CAL observations; raw source pins checked once."""
    spec = contract['sequences'][dataset]
    original = json.loads(pinned(spec['calibrated_provider_bundle'], reg).read_text())
    root = stage/'02_SEQUENCE_PROVIDERS'/dataset
    root.mkdir(parents=True, exist_ok=False)
    raw = {}
    for role, pin in spec['raw_inputs'].items():
        source = pinned(pin, reg)
        raw[role] = {'path': str(source), 'sha256': pin['sha256']}
    providers = {}
    for role, pin in spec['providers'].items():
        source = pinned(pin, reg)
        destination = root/source.name
        with source.open('rb') as reader, destination.open('xb') as writer:
            shutil.copyfileobj(reader, writer, 1024*1024)
        if sha256_file(destination) != pin['sha256']:
            raise ValueError('Sequence provider copy changed bytes')
        providers[role] = {**pin, 'path': str(destination)}
    bundle = {**FLAGS, 'providers': providers, 'raw_input_hashes': raw,
              'dataset_id': dataset, 'data_mode': spec['data_mode'], 'code_commit': code_commit,
              'frozen_source_bundle': spec['calibrated_provider_bundle'],
              'source_raw_hashes': original.get('raw_source_hashes'), 'byte_identity': True}
    write_json(root/'PROVIDER_BUNDLE.json', bundle)
    return bundle


def provider_child(args):
    from .providers import generate_one
    contract, reg = load_contract(args.contract), registry(args.local_config)
    stage = resolve(contract['stage_root'], reg)
    freeze = json.loads(active_freeze_path(stage, contract).read_text())
    if args.code_commit != freeze['code_commit'] or sha256_file(args.contract) != freeze['contract_hash']:
        raise ValueError('Provider child requires the existing committed execution freeze')
    if args.case_id in ('BY2H', 'BY2O'):
        sequence_bundle(contract, reg, stage, args.case_id, args.code_commit)
    else:
        generate_one(contract, reg, stage, args.case_id, args.code_commit, sha256_file(args.contract))


def provider_task(case_id, contract, reg, stage, code_commit, args):
    root = stage/'01_PROVIDER_AUDIT'/case_id
    root.mkdir(parents=True, exist_ok=False)
    tmp = root/'tmp'
    tmp.mkdir()
    log = root/'PROVIDER_OPENAT.strace'
    command = ['env', 'PYTHONDONTWRITEBYTECODE=1', 'PYTHONPATH='+str(reg.code_root/'src'),
        'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1', 'NUMEXPR_NUM_THREADS=1',
        'TMPDIR='+str(tmp), 'MPLCONFIGDIR='+str(tmp), 'XDG_CACHE_HOME='+str(tmp),
        'strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat', '-o', str(log),
        sys.executable, str(reg.code_root/'scripts/paper_rebuild/clean6_run_canonical541_v2.py'),
        '--operation', 'provider', '--local-config', args.local_config, '--contract', args.contract,
        '--case-id', case_id, '--code-commit', code_commit]
    started = time.monotonic()
    result = run_process_group(command, cwd=reg.code_root, timeout_seconds=1800,
        timeout_message='P09c provider timeout; no retry', launch_failure_message='P09c provider launch failure')
    (root/'stdout.log').write_text(result.stdout)
    (root/'stderr.log').write_text(result.stderr)
    opened = audited_open_records(log, reg.code_root)
    forbidden = [r for r in opened if Path(r['path']).name.lower().startswith('trace_') or
                 Path(r['path']).suffix.lower() in ('.bag', '.fpl')]
    output = stage/'02_SEQUENCE_PROVIDERS'/case_id if case_id in ('BY2H', 'BY2O') else stage/'02_PROVIDERS'/case_id
    scope = write_scope_audit(opened, raw_root=reg.raw_root, clean_root=reg.clean_root,
                              allowed_write_roots=[root, output])
    raw = [r for r in opened if reg.raw_root in Path(r['path']).parents]
    if case_id in ('BY2H', 'BY2O'):
        allowed_raw = {str(resolve(p['path'], reg)) for p in contract['sequences'][case_id]['raw_inputs'].values()}
    else:
        allowed_raw = set()
    passed = (result.returncode == 0 and not forbidden and scope['pass'] and
              all(r['path'] in allowed_raw and 'O_RDONLY' in r['flags'] and r['return_code'] >= 0 for r in raw))
    audit = {'status': 'PASS' if passed else 'FAIL', 'case_id': case_id, 'exit_code': result.returncode,
             'forbidden_open_count': len(forbidden), 'raw_open_count': len(raw), 'scope': scope,
             'runtime_seconds': time.monotonic()-started, 'strace_sha256': sha256_file(log)}
    write_json(root/'PROVIDER_AUDIT.json', audit)
    if not passed:
        raise RuntimeError('Provider failed; preserve scene: '+case_id+' '+result.stderr[-1200:])
    name = 'PROVIDER_BUNDLE.json'
    bundle = json.loads((output/name).read_text())
    for pin in bundle['providers'].values(): pinned(pin, reg)
    write_json(root/'PROVIDER_OUTPUT_SEAL.json', {'files': inventory(output), 'status': 'SEALED'})
    print('PROVIDER', case_id, 'PASS', flush=True)
    return bundle


def create_jobs(contract, reg, runs, cases):
    case_lookup = {r['case_id']: r for r in cases}
    c00 = [r for r in runs if r['case_id'] == 'C00_clean_normal']
    by_method = {r['method_id']: r for r in c00}
    jobs = [{'source': r, 'dataset': 'BY2', 'case_meta': case_lookup[r['case_id']]} for r in c00]
    for dataset in ('BY2H', 'BY2O'):
        spec = contract['sequences'][dataset]
        for method in contract['runtime']['profiles']:
            row = {**by_method[method], 'run_id': f'SEQUENCE_{dataset}_{method}',
                   'case_id': spec['case_id'], 'case_family': 'natural_sequence',
                   'degradation_type_id': 'CLEAN', 'seed_index': ''}
            jobs.append({'source': row, 'dataset': dataset, 'case_meta': spec['case_meta']})
    jobs.extend({'source': r, 'dataset': 'BY2', 'case_meta': case_lookup[r['case_id']]}
                for r in runs if r['case_id'] != 'C00_clean_normal')
    if len(jobs) != 5973 or len({j['source']['run_id'] for j in jobs}) != 5973:
        raise ValueError('Distinct run registry failed')
    return jobs


def execute_job(job, bundles, contract, reg, scratch_batch, code_commit, c00):
    source, dataset = job['source'], job['dataset']
    template = None
    if dataset != 'BY2':
        originals = contract['sequences'][dataset]['original_configs']
        method = source['method_id']
        pin = originals.get(method, originals['F04'])
        template = pinned({'path': pin['runtime_config'], 'sha256': pin['runtime_config_sha256']}, reg).read_text()
        if method not in originals:
            full = Path(c00['F04']['runtime_config_path']).read_text()
            variant = Path(c00[method]['runtime_config_path']).read_text()
            template, changes = profile_template(template, full, variant)
    bundle = bundles[source['case_id'] if dataset == 'BY2' else dataset]
    result = run_one(source, bundle, contract, reg, scratch_batch/'03_RUNS'/source['run_id'],
                     code_commit, original_text=template, dataset=dataset,
                     sequence_spec=contract['sequences'][dataset], case_meta=job['case_meta'])
    print('SOLVER', dataset, source['run_id'], result['terminal_status'], flush=True)
    return result


def anchor_gate(records, contract):
    lookup = {(r['dataset_id'], r['method_id']): r for r in records}
    refs = [('P07_C00', 'BY2', r) for r in contract['anchors']['C00_profiles']]
    refs += [('P06_CAL', r['dataset_id'], r) for r in contract['sequence_consistency']['references']]
    checks = []
    for origin, dataset, ref in refs:
        row = lookup.get((dataset, ref['method_id']))
        for name, expected in ref['files_sha256'].items():
            actual = row.get('output_seal', {}).get(name, {}).get('sha256') if row else None
            checks.append({'origin': origin, 'dataset_id': dataset, 'method_id': ref['method_id'],
                           'file': name, 'expected_sha256': expected, 'actual_sha256': actual,
                           'byte_equal': actual == expected})
    closed = (len(records) == 33 and len(lookup) == 33 and
              all(r['terminal_status'] == 'COMPLETED' for r in records) and
              len({r['code_commit'] for r in records}) == 1)
    return {'status': 'PASS' if closed and all(c['byte_equal'] for c in checks) else 'FAIL',
            'sequence_runs': len(records), 'all_33_completed_same_freeze': closed,
            'P07_C00_profiles': 11, 'P06_reference_runs': 15,
            'file_comparisons': len(checks), 'matching_files': sum(c['byte_equal'] for c in checks),
            'checks': checks}


def run_group(jobs, pool, bundles, contract, reg, scratch_batch, code_commit, c00):
    futures = [pool.submit(execute_job, job, bundles, contract, reg, scratch_batch, code_commit, c00) for job in jobs]
    records = []
    for future in as_completed(futures): records.append(future.result())
    records.sort(key=lambda r: next(i for i, job in enumerate(jobs) if job['source']['run_id'] == r['run_id']))
    return records


def evaluate_batch(records, contract, reg, scratch_batch, code_commit, output, solver_peak):
    """Use registered evaluations for RSS measurement; never rerun a probe."""
    from .evaluation import one_evaluation
    tasks = [(record, version) for record in records for version in ('v3', 'v2')]
    completed = []
    rss_peak = 0
    initial = machine_state()
    plans = []
    prior = resolve(contract['stage_root'], reg)/'PILOT_GATE.json'
    if prior.is_file():
        rss_peak = json.loads(prior.read_text())['evaluator_peak_rss_bytes']
    else:
        probes = []
        for dataset in ('BY2', 'BY2H', 'BY2O'):
            record = next(r for r in records if r['dataset_id'] == dataset and r['terminal_status'] == 'COMPLETED')
            probes.extend((record, version) for version in ('v3', 'v2'))
        for record, version in probes:
            # A single measured probe precedes allocation of the evaluator pool.
            # Recheck the known memory bound before all subsequent probes.
            if rss_peak:
                choose_evaluator_workers(machine_state()['memory_available_bytes'], solver_peak, rss_peak, initial['nproc'])
            row = one_evaluation(record, version, contract, reg, scratch_batch, code_commit)
            completed.append(row)
            write_json(output/f'EVALUATION_PROBE_{len(completed):02d}.json', row)
            if row['evaluation_status'] != 'COMPLETED':
                raise RuntimeError('Registered evaluator RSS probe failed; no retry')
            rss_peak = max(rss_peak, row['evaluator_peak_rss_bytes'])
            tasks.remove((record, version))
            print('EVALUATOR_PROBE', row['run_id'], version, row['evaluation_runtime_seconds'], row['evaluator_peak_rss_bytes'], flush=True)
    permitted = {'COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE'}
    while tasks:
        state = machine_state()
        count = choose_evaluator_workers(state['memory_available_bytes'], solver_peak, rss_peak, state['nproc'])
        wave, tasks = tasks[:count], tasks[count:]
        plan = {'wave': len(plans)+1, 'workers': count, 'available_memory_bytes': state['memory_available_bytes'],
                'solver_peak_bytes': solver_peak, 'measured_evaluator_peak_rss_bytes': rss_peak,
                'reserved_peak_bytes': solver_peak+count*rss_peak*1.25,
                'memory_budget_bytes': state['memory_available_bytes']*.75}
        plans.append(plan)
        append_json(output/'EVALUATOR_POOL_LEDGER.jsonl', plan)
        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = [pool.submit(one_evaluation, r, v, contract, reg, scratch_batch, code_commit) for r, v in wave]
            results = [future.result() for future in as_completed(futures)]
        completed.extend(results)
        write_json(output/f'EVALUATION_WAVE_{len(plans):04d}.json', results)
        if any(row['evaluation_status'] not in permitted for row in results):
            raise RuntimeError('Evaluation wave failed; no next wave, retry or cleanup')
        rss_peak = max([rss_peak]+[r['evaluator_peak_rss_bytes'] for r in results if r['evaluation_status'] == 'COMPLETED'])
        if solver_peak+count*rss_peak*1.25 > plan['memory_budget_bytes']:
            raise RuntimeError('Measured evaluator RSS exceeded registered 75% memory budget; retain scene')
        print('EVALUATION_WAVE', len(plans), 'COMPLETE', len(completed), 'POOL', count, flush=True)
    return completed, {'initial_machine': initial, 'solver_peak_bytes': solver_peak,
                       'evaluator_peak_rss_bytes': rss_peak, 'wave_plans': plans,
                       'evaluator_pool_sizes': sorted({p['workers'] for p in plans})}


def do_batch(batch_number, jobs, contract, reg, stage, scratch, code_commit, args, workers, c00,
             *, resumed_records=None):
    from .evaluation import one_evaluation
    batch_write_json, batch_append_json = write_json, append_json
    if getattr(args, 'io_context', None) is not None:
        from .io_recovery import write_json as batch_write_json, append_json as batch_append_json
    batch_id = f'BATCH_{batch_number:03d}'
    output = stage/'BATCHES'/batch_id
    output.mkdir(parents=True, exist_ok=resumed_records is not None)
    scratch_batch = scratch/batch_id
    scratch_batch.mkdir(parents=True, exist_ok=resumed_records is not None)
    original_allocated = sum(p.stat().st_blocks*512 for p in scratch_batch.rglob('*') if p.is_file())
    batch_append_json(stage/'BATCH_LEDGER.jsonl', {'event': 'BATCH_START', 'batch': batch_number,
        'workers': workers, 'run_count': len(jobs), 'utc': now(), 'code_commit': code_commit})
    all_records, evaluations, receipts = [], [], []
    io_archive = None
    sample_name = 'RESOURCE_SAMPLES_RESTART.jsonl' if resumed_records is not None else 'RESOURCE_SAMPLES.jsonl'
    with ResourceMonitor(scratch, reg.clean_root, output/sample_name) as monitor:
        monitor.begin_phase('providers')
        with ThreadPoolExecutor(max_workers=workers) as pool:
            keys = list(dict.fromkeys(j['source']['case_id'] if j['dataset'] == 'BY2' else j['dataset'] for j in jobs))
            bundles, pending = {}, {}
            for key in keys:
                root = stage/('02_SEQUENCE_PROVIDERS' if key in ('BY2H', 'BY2O') else '02_PROVIDERS')/key
                name = 'PROVIDER_BUNDLE.json'
                if (root/name).is_file():
                    audit = json.loads((stage/'01_PROVIDER_AUDIT'/key/'PROVIDER_AUDIT.json').read_text())
                    if audit['status'] != 'PASS': raise ValueError('Prior provider terminal not PASS')
                    bundles[key] = json.loads((root/name).read_text())
                    for pin in bundles[key]['providers'].values(): pinned(pin, reg)
                else:
                    pending[pool.submit(provider_task, key, contract, reg, stage, code_commit, args)] = key
            for future in as_completed(pending): bundles[pending[future]] = future.result()
            monitor.end_phase()
            monitor.begin_phase('solver')
            groups = (jobs[:33], jobs[33:]) if batch_number == 1 else (jobs,)
            for index, group in enumerate(groups):
                reuse = resumed_records is not None and index == 0
                records = resumed_records if reuse else run_group(group, pool, bundles, contract, reg, scratch_batch, code_commit, c00)
                all_records.extend(records)
                group_name = f'SOLVER_GROUP_{index}_REVALIDATED.json' if reuse else f'SOLVER_GROUP_{index}.json'
                batch_write_json(output/group_name, records)
                if batch_number == 1 and index == 0:
                    gate = anchor_gate(records, contract)
                    gate_root = restart_root(stage, contract) if resumed_records is not None else stage
                    gate_path = gate_root/'SEQUENCE_CONSISTENCY_GATE.json'
                    if gate_path.exists():
                        if json.loads(gate_path.read_text()) != gate:
                            raise ValueError('Revalidated sequence gate changed before remaining pilot solves')
                    else:
                        batch_write_json(gate_path, gate)
                    if gate['status'] != 'PASS':
                        raise RuntimeError('Sequence/C00 byte gate failed; no remaining pilot solver launched')
                if any(r['terminal_status'] == 'FAILED_TECHNICAL' for r in records):
                    raise RuntimeError('Technical solver failure; batch stopped, no retry or cleanup')
            solver_measurements = monitor.end_phase()
            monitor.begin_phase('evaluation')
            evaluations, resource_plan = evaluate_batch(all_records, contract, reg, scratch_batch, code_commit,
                output, solver_measurements['owned_process_tree_peak_rss_bytes'])
            batch_write_json(output/'RESOURCE_POOL_PLAN.json', resource_plan)
            monitor.end_phase()
            monitor.begin_phase('archive_cleanup')
            batch_write_json(output/'SOLVER_RECORDS_BEFORE_ARCHIVE.json', all_records)
            batch_write_json(output/'EVALUATION_RECORDS_BEFORE_ARCHIVE.json', evaluations)
            permitted = {'PASS', 'COMPLETED', 'SUCCESS', 'NOT_RUN_ALGORITHM_FAILURE'}
            if any(r['evaluation_status'] not in permitted for r in evaluations):
                raise RuntimeError('Evaluation or WGS84 self-check failed; retain full batch scene')
            io_context = getattr(args, 'io_context', None)
            if io_context is not None:
                from .io_recovery import archive_batch
                all_records, evaluations, receipts, io_archive = archive_batch(
                    all_records, evaluations, context=io_context, scratch_batch=scratch_batch,
                    output=output, batch_number=batch_number, monitor=monitor)
            else:
                pending_archive = {}
                for record in all_records:
                    roots = {v: scratch_batch/'12_OFFLINE_EVALUATION'/v/record['run_id'] for v in ('v3', 'v2')}
                    destination = stage/'RETAINED_RUNS'/record['run_id']
                    pending_archive[pool.submit(retain_run, record, roots, destination)] = (record, roots)
                archive_pairs = []
                for future in as_completed(pending_archive):
                    receipt = future.result()
                    record, roots = pending_archive[future]
                    receipts.append(receipt)
                    archive_pairs.append((record, roots, receipt))
                    print('ARCHIVED', record['run_id'], receipt['retained_bytes'], flush=True)
                batch_write_json(output/'ARCHIVE_RECEIPTS.json', receipts)
                for record in all_records:
                    destination = stage/'RETAINED_RUNS'/record['run_id']
                    record['scratch_output_root'] = record['output_root']
                    record['output_root'] = str(destination/'solver')
                    record['archive_receipt'] = str(destination/'ARCHIVE_RECEIPT.json')
                for row in evaluations:
                    run_id, version = row['run_id'], row['evaluator_version']
                    destination = stage/'RETAINED_RUNS'/run_id
                    original_eval = scratch_batch/'12_OFFLINE_EVALUATION'/version/run_id
                    for key in ('evaluation_output_root', 'source_row', 'error_series_source', 'summary_source'):
                        if row.get(key):
                            path = Path(row[key])
                            if not path.is_relative_to(original_eval):
                                raise ValueError('Evaluation artifact path escapes run: '+key)
                            row[key] = str(destination/version/path.relative_to(original_eval))
                    row['output_root'] = str(destination/'solver')
                    row['native_run_manifest'] = str(destination/'solver/RUN_MANIFEST.json')
                batch_write_json(output/'RUN_RECORDS.json', all_records)
                batch_write_json(output/'EVALUATION_RECORDS.json', evaluations)
                # Whole-batch archive barrier before the first unlink.
                monitor.assert_healthy()
                batch_write_json(output/'BATCH_ARCHIVE_GATE.json', {'status': 'PASS', 'run_count': len(receipts)})
                for record, roots, receipt in archive_pairs:
                    monitor.assert_healthy()
                    for role, root in [('solver', Path(record['scratch_output_root'])), *roots.items()]:
                        cleanup_exact(root, receipt['original_files'][role], output/'CLEANUP_LEDGER.jsonl',
                                      scratch_root=scratch, archive_verified=True)
                batch_write_json(output/'CLEANUP_COMPLETE.json', {'status': 'PASS', 'run_count': len(receipts)})
            monitor.end_phase()
    measurements = monitor.result()
    result = {'status': io_archive['status'] if io_archive else 'PASS', 'batch': batch_number, 'workers': workers,
              'run_count': len(all_records), 'evaluation_count': len(evaluations),
              'terminal_counts': {s: sum(r['terminal_status'] == s for r in all_records)
                                  for s in sorted({r['terminal_status'] for r in all_records})},
              'measurements': measurements,
              'resource_pool_plan': resource_plan,
              'original_scratch_allocated_bytes': original_allocated,
              'run_measurements': [{'run_id': r['run_id'], 'runtime_seconds': r['runtime_seconds'],
                  'solver_seconds': r.get('solver_seconds'), 'solver_output_bytes': r['solver_output_bytes'],
                  'solver_peak_rss_bytes': r.get('solver_peak_rss_bytes'),
                  'evaluation_seconds': {v: next(e.get('evaluation_runtime_seconds') for e in evaluations
                      if e['run_id'] == r['run_id'] and e['evaluator_version'] == v) for v in ('v3', 'v2')},
                  'evaluation_peak_rss_bytes': {v: next(e.get('evaluator_peak_rss_bytes') for e in evaluations
                      if e['run_id'] == r['run_id'] and e['evaluator_version'] == v) for v in ('v3', 'v2')},
                  **{k: next((p[k] for p in receipts if p['run_id'] == r['run_id']), None)
                     for k in ('source_bytes', 'retained_bytes', 'retained_allocated_bytes')}} for r in all_records]}
    if io_archive is not None:
        phase = measurements['phases'][-1]
        result.update(archive=io_archive, scientific_code_commit=code_commit,
            io_fix_code_commit=io_context['freeze']['io_fix_code_commit'],
            io_bottleneck=measurements['cpu_utilization_fraction'] is not None and measurements['cpu_utilization_fraction'] < .40,
            archive_phase_cpu_utilization_fraction=phase['cpu_utilization_fraction'],
            io_bottleneck_definition='batch visible-affinity CPU utilization below 40%; primary_io_cost is largest measured archive component, not a provider bottleneck claim')
        batch_append_json(Path(io_context['root'])/'IO_BATCH_LEDGER.jsonl', {'event': 'BATCH_COMPLETE', 'utc': now(), **result})
    batch_write_json(output/'BATCH_RESULT.json', result)
    batch_append_json(stage/'BATCH_LEDGER.jsonl', {'event': 'BATCH_COMPLETE', 'utc': now(), **result})
    if batch_number == 1:
        fixed = sum(p.stat().st_blocks*512 for sub in ('02_PROVIDERS', '02_SEQUENCE_PROVIDERS', '01_PROVIDER_AUDIT')
                    for p in (stage/sub).rglob('*') if p.is_file())
        peak = 1.15*(max(p['retained_allocated_bytes'] for p in receipts)*5973 + original_allocated +
                     measurements['filesystem_peak_growth_bytes']['scratch'] + fixed*541/max(1, len(keys)))
        passed = peak <= contract['storage']['peak_limit_bytes']
        prior_wall = 0.
        if resumed_records is not None:
            old_report = json.loads((stage/'99_STOP_REPORT/STOP_REPORT.json').read_text())
            # Original attempts and restart are reported separately; sum active
            # wall time only, never count the human pause as batch execution.
            prior_wall = old_report['execution_prefix_wall_seconds']
        pilot = {'status': 'PASS' if passed else 'STOP_PROJECTED_PEAK',
                 'projected_peak_bytes': math.ceil(peak),
                 'projected_wall_seconds': (measurements['wall_seconds']+prior_wall)*math.ceil(5973/256),
                 'batch_active_wall_seconds': measurements['wall_seconds']+prior_wall,
                 'original_prefix_wall_seconds': prior_wall,
                 'forecast_kind': 'conditional conservative planning extrapolation; not CI or measured full runtime',
                 'forecast_formula': contract['storage'].get('forecast_formula', '1.15*(max retained allocation*5973 + scratch peak + scaled fixed provider footprint)'),
                 'next_workers': workers, 'measurements': measurements,
                 'evaluator_peak_rss_bytes': resource_plan['evaluator_peak_rss_bytes'],
                 'resource_pool_plan': resource_plan,
                 'sequence_consistency_gate': 'PASS', 'batch_verification': 'PASS'}
        batch_write_json(stage/'PILOT_GATE.json', pilot)
        print('PILOT_GATE', json.dumps(pilot, ensure_ascii=False), flush=True)
        if not passed: raise RuntimeError('Pilot projected peak exceeds 250 GB; no continuation')
    return result


def prepare_restart(contract, reg, stage, scratch, args, jobs):
    """The only authorized reuse path; original 33 native identities stay sealed."""
    from .revalidation import revalidate_existing
    amendment = contract['restart_authorization']
    target = restart_root(stage, contract)
    if target.exists():
        raise FileExistsError('Restart identity already exists; no automatic retry')
    freeze = verify_preregistration(Path(args.contract).resolve(), reg.code_root)
    subprocess.run(['git', 'merge-base', '--is-ancestor', amendment['starting_commit'], freeze['code_commit']],
                   cwd=reg.code_root, check=True)
    for pin in amendment['retained_evidence_pins'].values():
        pinned(pin, reg)
    original = json.loads((stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json').read_text())
    if (original['code_commit'] != amendment['original_execution_code_commit'] or
            original['contract_hash'] != amendment['original_contract_sha256']):
        raise ValueError('Original native code/contract identity changed')
    if scratch != Path(original['scratch_root']):
        raise ValueError('Restart scratch differs from original frozen scratch root')
    allowed = {'src/legsa_gins/paper_rebuild/clean6_canonical_v2/'+name+'.py'
               for name in ('runner', 'runtime', 'storage', 'evaluation', 'contract', 'pack')}
    allowed.update(('src/legsa_gins/paper_rebuild/clean5_degradation/runtime.py',
                    'src/legsa_gins/paper_rebuild/clean5_sequence/evaluation_process.py',
                    str(Path(args.contract).resolve().relative_to(reg.code_root))))
    changed = []
    for relative, digest in original['source_sha256'].items():
        if sha256_file(reg.code_root/relative) != digest:
            if relative not in allowed:
                raise ValueError('Restart changed frozen source outside authorized repair: '+relative)
            changed.append(relative)
    for pin in (contract['runtime']['executable'], contract['runtime']['model'], contract['evaluation']['evaluator'],
                contract['anchors']['C00_reference_seal'], contract['sequence_consistency']['reference_seal']):
        pinned(pin, reg)
    if shutil.disk_usage(reg.clean_root).free < 300_000_000_000 or shutil.disk_usage(scratch).free < 150_000_000_000:
        raise ValueError('Restart G/ext4 free-space gate failed')
    original_records = json.loads((stage/'BATCHES/BATCH_001/SOLVER_GROUP_0.json').read_text())
    if ([r['run_id'] for r in original_records] != [j['source']['run_id'] for j in jobs[:33]] or
            any(r['exit_code'] != 0 for r in original_records)):
        raise ValueError('Original 33 sealed exit-zero registry changed')
    if any(Path(r['output_root']) != scratch/'BATCH_001/03_RUNS'/r['run_id'] for r in original_records):
        raise ValueError('Original run output root differs from exact frozen batch/run path')
    if any((scratch/'BATCH_001/03_RUNS'/j['source']['run_id']).exists() for j in jobs[33:]):
        raise ValueError('Unexpected already-started run; no automatic rerun')
    target.mkdir(parents=True, exist_ok=False)
    freeze.update(source_sha256=freeze_sources(reg.code_root), started_utc=now(),
                  machine=machine_state(), scratch_root=str(scratch), original_execution_freeze=original,
                  authorized_changed_source_paths=sorted(changed), original_native_reused_count=33, **FLAGS)
    write_json(target/'CONTINUATION_FREEZE.json', freeze)
    try:
        checkpoint(contract, reg, target, 'PRE_RESTART', {'mode': 'independent_hash_all',
            'human_instruction': 'P09c explicit restart independent raw integrity checkpoint'})
        records = revalidate_existing(original_records, contract, reg, target, freeze['code_commit'])
        gate = anchor_gate(records, contract)
        write_json(target/'SEQUENCE_CONSISTENCY_GATE.json', gate)
        if gate['status'] != 'PASS':
            raise ValueError('Revalidated sequence/C00 byte gate failed; no remaining solver')
        append_json(stage/'BATCH_LEDGER.jsonl', {'event': 'AUTHORIZED_REVALIDATION_PASS', 'utc': now(),
            'reused_native_runs': 33, 'revalidated_runs': 22, 'matching_files': gate['matching_files'],
            'native_code_commit': original['code_commit'], 'validation_code_commit': freeze['code_commit']})
        print('REVALIDATED_SEQUENCE_GATE', json.dumps({k:v for k,v in gate.items() if k != 'checks'}), flush=True)
        return freeze, records
    except Exception as error:
        write_json(target/'STOPPED.json', {'status': 'STOPPED_GATE_FAILURE', 'reason': str(error),
            'utc': now(), 'retry_count': 0, 'scene_retained': True, 'original_native_reruns': 0})
        append_json(stage/'BATCH_LEDGER.jsonl', {'event': 'RESTART_STOPPED', 'utc': now(), 'reason': str(error)})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--operation', choices=('start', 'restart', 'continue', 'provider'), default='start')
    parser.add_argument('--case-id')
    parser.add_argument('--code-commit')
    parser.add_argument('--stop-after-batch', type=int, default=1)
    args = parser.parse_args(argv)
    args.contract = str(Path(args.contract).resolve())
    args.local_config = str(Path(args.local_config).resolve())
    if args.operation == 'provider':
        provider_child(args)
        return 0
    contract, reg = load_contract(args.contract), registry(args.local_config)
    stage = resolve(contract['stage_root'], reg)
    paths = yaml.safe_load(Path(args.local_config).read_text())['paths']
    scratch = Path(paths['canonical541_v2_scratch'])
    if stage.name != STAGE_NAME or not stage.is_relative_to(reg.clean_root):
        raise ValueError('Unexpected protected stage root')
    if any(p.is_symlink() for p in (scratch, *scratch.parents)):
        raise ValueError('Scratch symlink prohibited')
    parent = next(p for p in (scratch, *scratch.parents) if p.exists())
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(parent)], text=True).strip()
    if filesystem != 'ext4': raise ValueError('Latest amendment requires WSL ext4 scratch')
    cases, runs = selection(contract, reg)
    jobs = create_jobs(contract, reg, runs, cases)
    c00 = {r['method_id']: r for r in runs if r['case_id'] == 'C00_clean_normal'}
    freeze_path = stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json'
    resolution = {'mode': 'independent_hash_all', 'human_instruction': 'P-09c based on P-08 preregistered independent pre/post hash-only checkpoints'}
    resumed_records = None
    if args.operation == 'restart':
        freeze, resumed_records = prepare_restart(contract, reg, stage, scratch, args, jobs)
        start = 1
    elif args.operation == 'start':
        freeze = verify_preregistration(Path(args.contract), reg.code_root)
        if stage.exists() or scratch.exists(): raise FileExistsError('Attempt exists; no automatic regeneration/retry')
        if shutil.disk_usage(reg.clean_root).free < 300_000_000_000:
            raise ValueError('G available below 300 GB; stop')
        if shutil.disk_usage(parent).free < 150_000_000_000:
            raise ValueError('Ext4 available below 150 GB; direct G fallback superseded')
        pinned(contract['runtime']['executable'], reg)
        pinned(contract['runtime']['model'], reg)
        pinned(contract['evaluation']['evaluator'], reg)
        pinned(contract['anchors']['C00_reference_seal'], reg)
        pinned(contract['sequence_consistency']['reference_seal'], reg)
        stage.mkdir(parents=True, exist_ok=False)
        scratch.mkdir(parents=True, exist_ok=False)
        freeze.update(source_sha256=freeze_sources(reg.code_root), started_utc=now(),
                      machine=machine_state(), scratch_root=str(scratch), **FLAGS)
        write_json(freeze_path, freeze)
        write_json(stage/'00_PREREGISTRATION/UNIQUE_JOBS.json', jobs)
        checkpoint(contract, reg, stage, 'PRE_EXECUTION', resolution)
        start = 1
    else:
        freeze = json.loads(active_freeze_path(stage, contract).read_text())
        validate_freeze(freeze, Path(args.contract), reg)
        pilot = json.loads((stage/'PILOT_GATE.json').read_text())
        if pilot['status'] != 'PASS': raise ValueError('Pilot not PASS; no continuation')
        completed = sorted((stage/'BATCHES').glob('BATCH_*/BATCH_RESULT.json'))
        start = len(completed)+1
        if any(json.loads(p.read_text())['status'] != 'PASS' for p in completed):
            raise ValueError('Prior batch not PASS')
    try:
        for number in range(start, min(args.stop_after_batch, math.ceil(len(jobs)/256))+1):
            validate_freeze(freeze, Path(args.contract), reg)
            workers = solver_workers(machine_state()['nproc'])
            do_batch(number, jobs[(number-1)*256:number*256], contract, reg, stage, scratch,
                     freeze['code_commit'], args, workers, c00,
                     resumed_records=resumed_records if number == 1 else None)
        if args.stop_after_batch >= math.ceil(len(jobs)/256):
            checkpoint(contract, reg, stage, 'POST_EXECUTION', resolution)
            write_json(stage/'EXECUTION_COMPLETE.json', {'status': 'EXECUTION_COMPLETE_PENDING_AGGREGATE',
                'run_count': 5973, 'code_commit': freeze['code_commit'], 'completed_utc': now()})
        print('VERIFIED_BATCH_BOUNDARY', min(args.stop_after_batch, math.ceil(len(jobs)/256)), flush=True)
        return 0
    except Exception as exc:
        append_json(stage/'BATCH_LEDGER.jsonl', {'event': 'STOPPED', 'utc': now(), 'exception': type(exc).__name__,
            'reason': str(exc), 'retry_count': 0, 'scene_retained': True})
        stop_root = restart_root(stage, contract) if restart_root(stage, contract).exists() else stage
        write_json(stop_root/'STOPPED.json', {'status': 'STOPPED_GATE_FAILURE', 'reason': str(exc),
            'retry_count': 0, 'scene_retained': True, 'utc': now()})
        raise


if __name__ == '__main__':
    raise SystemExit(main())
