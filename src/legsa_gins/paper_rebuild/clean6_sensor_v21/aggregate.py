"""P-13 tables from supplied sealed indices; no raw/trace or evaluator calls.

Canonical and addendum statistics retain their original pure implementations.
Only counting, protocol provenance, comparison joins, and H7-H11 reporting are
new. Missing statistics stay unavailable and never acquire a numeric delta.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_degradation.common import write_json, resolve
from ..clean5_sequence import evaluation_tables as sequence
from ..clean6_addendum import aggregate as addendum
from ..clean6_canonical_v2 import aggregate as v2
from ..clean6_canonical_v2.io_recovery import ScientificStop
from ..manifest import sha256_file

VERSIONS = ('v3', 'v2')
DATASETS = ('BY2', 'BY2H', 'BY2O')
C00 = 'C00_clean_normal'
ALGORITHM_FAILURE = 'ALGORITHM_FAILURE_ALL_YAW_REJECTED'
EXTRA_METRICS = ('yaw_abs_error_over_std_median', 'yaw_DOWNWEIGHT', 'yaw_REJECT',
                 'yaw_DOWNWEIGHT_plus_REJECT', 'outage_end_horizontal_error_m',
                 'max_horizontal_error_in_window_m')


def load_baseline_indices(v2_contract, addendum_contract, reg):
    """Read exact current v2 terminal indices, hash-verified from published seals.

    This helper performs only row loading/identity joins. It writes no file and
    does not run aggregation or read NAV, STD, error series, or raw references.
    Returned core indices already include the 33 natural-sequence/C00 entries
    once (11 overlap core C00); addendum contributes 495 distinct records.
    """
    core_root = resolve(v2_contract['stage_root'], reg)
    add_root = resolve(addendum_contract['stage_root'], reg)
    source_pins = []
    def checked(path, expected=None):
        path = Path(path)
        if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Unsafe frozen index path')
        if path.suffix not in ('.csv', '.json') or not (path.is_relative_to(reg.clean_root) or path.is_relative_to(reg.code_root)):
            raise ValueError('Frozen baseline loader is restricted to named clean JSON/CSV indices')
        digest = sha256_file(path)
        if expected is not None and digest != expected:
            raise ValueError('Frozen v2 index SHA mismatch: '+str(path))
        source_pins.append({'path': str(path), 'sha256': digest, 'expected_sha256': expected,
                            'role': 'frozen_v2_index_or_published_seal', 'size_bytes': path.stat().st_size})
        return path
    evidence_path = checked(reg.code_root/'docs/paper_rebuild/clean6/P09C_PROTOCOL_V2_FINAL_EVIDENCE.csv')
    with evidence_path.open(newline='') as stream:
        evidence = {r['path']: r for r in csv.DictReader(stream)}
    paths = {}
    for name in ('FULL_RUN_RECORDS.json', 'FULL_EVALUATION_RECORDS.json'):
        alias = '<CANONICAL541_V2_ROOT>/IO_RECOVERY/IO_RECOVERY_20260912/'+name
        pin = evidence[alias]
        paths[name] = checked(core_root/'IO_RECOVERY/IO_RECOVERY_20260912'/name, pin['sha256'])
    native = json.loads(paths['FULL_RUN_RECORDS.json'].read_text())
    evaluations = json.loads(paths['FULL_EVALUATION_RECORDS.json'].read_text())
    if len(native) != 5973 or len(evaluations) != 11946:
        raise ValueError('Frozen P09c complete index counts differ')
    add_evidence_path = checked(reg.code_root/'docs/paper_rebuild/clean6/ADDENDUM_A1_A2_EVIDENCE.csv')
    with add_evidence_path.open(newline='') as stream:
        add_evidence = {r['source']: r for r in csv.DictReader(stream)}
    seal_path = checked(add_root/'FINAL_RECORD_SEAL.json', add_evidence['<ADDENDUM_ROOT>/FINAL_RECORD_SEAL.json']['sha256'])
    seal = json.loads(seal_path.read_text())
    if seal['status'] != 'SEALED':
        raise ValueError('Frozen addendum record seal is not terminal')
    add_native, add_evaluations = [], []
    for batch in range(1, 6):
        prefix = 'CONTINUATIONS/ARCHIVE_IO_20260913/' if batch == 1 else ''
        directory = prefix+f'BATCHES/BATCH_{batch:03d}/'
        for name, target in (('RESOLVED_RUN_RECORDS.json', add_native), ('RESOLVED_EVALUATION_RECORDS.json', add_evaluations)):
            relative = directory+name
            path = checked(add_root/relative, seal['files'][relative]['sha256'])
            target.extend(json.loads(path.read_text()))
    if len(add_native) != 495 or len(add_evaluations) != 990:
        raise ValueError('Frozen addendum complete index counts differ')
    native.extend(add_native)
    evaluations.extend(add_evaluations)
    if len({(r.get('dataset_id', 'BY2'), r['case_id'], r['method_id']) for r in native}) != len(native):
        raise ValueError('Frozen native baseline identities overlap')
    if len({row_key(r) for r in evaluations}) != len(evaluations):
        raise ValueError('Frozen evaluation baseline identities overlap')
    return {'records': native, 'evaluations': evaluations, 'input_pins': source_pins,
            'native_count': len(native), 'evaluation_count': len(evaluations),
            'F01_native_count': sum(r['method_id'] == 'F01' for r in native),
            'aggregation_executed': False, 'scientific_execution_count': 0}


def _hash_rows(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _version(row):
    value = row.get('evaluator_version') or str(row.get('evaluator_contract', '')).removeprefix('evaluator_contract_')
    if value not in VERSIONS:
        raise ValueError('Explicit v3/v2 evaluator identity required')
    return value


def row_key(row):
    return (_version(row), row.get('dataset_id', 'BY2'), row['case_id'], row['method_id'])


def _domain(row):
    if row.get('dataset_id', 'BY2') != 'BY2':
        return 'SEQUENCE'
    if str(row['case_id']).startswith(('D61_', 'D62_')):
        return 'ADDENDUM'
    return 'CORE'


def _finite(value):
    if value in (None, '', 'UNAVAILABLE') or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def _success(row):
    return row is not None and row.get('evaluation_status') == 'COMPLETED'


def _status(row):
    if row is None:
        return 'MISSING'
    if row.get('solver_terminal_status', row.get('terminal_status')) == ALGORITHM_FAILURE:
        return 'ALGORITHM_FAILURE'
    return 'COMPLETED' if _success(row) else str(row.get('evaluation_status', 'UNAVAILABLE'))


def _duration(row, cases):
    case = cases.get(row['case_id'], {})
    for data in (row, case):
        if _finite(data.get('duration_s')) is not None:
            return _finite(data['duration_s'])
        params = data.get('degradation_parameters_json')
        if isinstance(params, str):
            params = json.loads(params or '{}')
        if isinstance(params, dict) and _finite(params.get('duration_s')) is not None:
            return _finite(params['duration_s'])
    return None


def normalize_rows(rows, *, supplements=(), cases=None):
    """Normalize explicit metadata and counter aliases, retaining metric values."""
    cases = cases or {}
    additional = {}
    for row in supplements:
        key = row_key(row)
        if key in additional:
            raise ValueError('Duplicate supplementary result identity')
        additional[key] = row
    output, seen = [], set()
    for source in rows:
        row = copy.deepcopy(source)
        key = row_key(row)
        if key in seen:
            raise ValueError('Duplicate evaluation identity; BY2 sequence/C00 must alias its core row: '+str(key))
        seen.add(key)
        row['evaluator_version'], row['dataset_id'] = key[:2]
        row['domain'] = _domain(row)
        meta = cases.get(row['case_id'], {})
        row.setdefault('case_family', meta.get('case_family', 'natural_sequence' if row['domain'] == 'SEQUENCE' else 'clean' if row['case_id'] == C00 else 'UNAVAILABLE'))
        row.setdefault('degradation_id', row.get('degradation_type_id', meta.get('degradation_type_id', 'CLEAN')))
        row.setdefault('seed_id', row.get('seed_index', meta.get('seed_index', '')))
        row.setdefault('effective_configuration_id', row.get('effective_profile'))
        row['duration_s'] = _duration(row, cases)
        for target, old_name in (('yaw_DOWNWEIGHT', 'scheme_c_downweight_count'), ('yaw_REJECT', 'scheme_c_reject_count')):
            if row.get(target) in (None, '') and row.get(old_name) not in (None, ''):
                row[target] = row[old_name]
        counter_values = [_finite(row.get(k)) for k in ('yaw_DOWNWEIGHT', 'yaw_REJECT')]
        row['yaw_DOWNWEIGHT_plus_REJECT'] = sum(counter_values) if all(v is not None for v in counter_values) else None
        if key in additional:
            extra = additional[key]
            for name, value in extra.items():
                if name in EXTRA_METRICS or '_consistency_' in name or name.endswith(('_std_nonfinite_count', '_std_nonpositive_count', '_error_nonfinite_count')):
                    if row.get(name) not in (None, '', 'UNAVAILABLE') and row[name] != value:
                        raise ValueError('Supplement would replace an existing metric: '+name)
                    row[name] = value
            row['supplementary_metric_provenance'] = {k: extra[k] for k in extra if k.endswith(('_source', '_sha256', '_definition'))}
        if row.get('evaluation_status') not in ('COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE'):
            raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE', 'Aggregate received failed evaluator '+str(key))
        if str(row.get('finite_output')).lower() == 'false' and row.get('evaluation_status') == 'COMPLETED':
            raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE', 'Aggregate received nonfinite completed row '+str(key))
        for name in (*canonical.PAIRWISE_METRICS, *EXTRA_METRICS):
            value = row.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(value):
                raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE', 'Aggregate received nonfinite metric '+name)
        if row.get('evaluation_status') == 'NOT_RUN_ALGORITHM_FAILURE':
            row['solver_terminal_status'] = ALGORITHM_FAILURE
        output.append(row)
    return output


def _metrics(rows):
    if not rows:
        return list(canonical.PAIRWISE_METRICS)+list(EXTRA_METRICS)
    union = {}
    for row in rows:
        union.update(row)
    found = v2._numeric_fields([union]+list(rows))
    ignored = {'duration_s', 'formal_F01_reused', 'original_native_reused', 'evaluator_repeat_calls',
               'solver_execution_count', 'evaluator_execution_count'}
    return list(dict.fromkeys((*canonical.PAIRWISE_METRICS, *EXTRA_METRICS, *(m for m in found if m not in ignored))))


def comparison_tables(old_rows, new_rows, profiles, *, cases=None, metrics=None):
    """Exact case joins before family/duration statistics; no failure deltas."""
    cases = cases or {}
    old_index, new_index = ({row_key(r): r for r in rows} for rows in (old_rows, new_rows))
    if len(old_index) != len(old_rows) or len(new_index) != len(new_rows):
        raise ValueError('Comparison identities are not unique')
    metrics = list(metrics or _metrics([*old_rows, *new_rows]))
    groups = defaultdict(list)
    for key in sorted(set(old_index) | set(new_index)):
        version, dataset, case_id, method = key
        if method not in profiles:
            continue
        old, new = old_index.get(key), new_index.get(key)
        meta = new or old
        domain, family = _domain(meta), meta.get('case_family', '')
        degradation, duration = meta.get('degradation_id', ''), _duration(meta, cases)
        identity = (version, domain, dataset, method)
        scopes = [('ALL', 'ALL', '', None), ('FAMILY', family, '', None),
                  ('DEGRADATION', family, degradation, None)]
        if duration is not None:
            scopes.append(('DURATION', family, degradation, duration))
        if case_id == C00 or domain == 'SEQUENCE':
            scopes.append(('CASE', case_id, degradation, duration))
        for scope in scopes:
            groups[identity+scope].append((key, old, new))
    comparison = []
    for group_key, members in sorted(groups.items(), key=lambda item: str(item[0])):
        version, domain, dataset, method, scope, family, degradation, duration = group_key
        base = {'evaluator_version': version, 'domain': domain, 'dataset_id': dataset,
                'method_id': method, 'scope': scope, 'family_or_case': family,
                'degradation_id': degradation, 'duration_s': duration, 'registered_case_count': len(members)}
        for metric in metrics:
            paired = [(key, _finite(a.get(metric)), _finite(b.get(metric))) for key, a, b in members
                      if _success(a) and _success(b) and _finite(a.get(metric)) is not None and _finite(b.get(metric)) is not None]
            old_available = sum(_success(a) and _finite(a.get(metric)) is not None for _, a, _ in members)
            new_available = sum(_success(b) and _finite(b.get(metric)) is not None for _, _, b in members)
            values = np.array([[a, b] for _, a, b in paired])
            for statistic in (('value',) if scope == 'CASE' else ('mean', 'median')):
                if len(paired):
                    a, b = values[0] if statistic == 'value' else (np.mean(values, axis=0) if statistic == 'mean' else np.median(values, axis=0))
                    old_value, new_value, delta = float(a), float(b), float(b-a)
                else:
                    old_value = new_value = delta = None
                comparison.append({**base, 'metric_name': metric, 'statistic': statistic,
                    'v2_value': old_value, 'v21_value': new_value, 'v21_minus_v2': delta,
                    'relative_change_percent': delta/abs(old_value)*100 if old_value not in (None, 0) else None,
                    'v2_available_count': old_available, 'v21_available_count': new_available,
                    'paired_finite_count': len(paired), 'v2_algorithm_failure_count': sum(_status(a) == 'ALGORITHM_FAILURE' for _, a, _ in members),
                    'v21_algorithm_failure_count': sum(_status(b) == 'ALGORITHM_FAILURE' for _, _, b in members),
                    'availability': 'AVAILABLE' if len(paired) == len(members) else 'PARTIAL' if paired else 'UNAVAILABLE',
                    'case_join': 'exact evaluator,dataset,case,method',
                    'statistic_population': 'same finite successful case pairs on both sides; missing/failures counted separately'})
    return comparison


def failure_comparison(old_rows, new_rows, profiles, *, cases=None):
    cases = cases or {}
    indices = [{row_key(r): r for r in rows} for rows in (old_rows, new_rows)]
    groups = defaultdict(list)
    for key in sorted(set(indices[0]) | set(indices[1])):
        if key[3] not in profiles:
            continue
        pair = tuple(index.get(key) for index in indices)
        row = pair[1] or pair[0]
        group = (_version(row), _domain(row), row['dataset_id'], row['method_id'],
                 row.get('case_family'), row.get('degradation_id'), _duration(row, cases))
        groups[group].append(pair)
    output = []
    for key, pairs in sorted(groups.items(), key=lambda item: str(item[0])):
        version, domain, dataset, method, family, degradation, duration = key
        old = Counter(_status(pair[0]) for pair in pairs)
        new = Counter(_status(pair[1]) for pair in pairs)
        output.append({'evaluator_version': version, 'domain': domain, 'dataset_id': dataset, 'method_id': method,
            'case_family': family, 'degradation_id': degradation, 'duration_s': duration,
            'registered_cases': len(pairs), 'v2_completed': old['COMPLETED'], 'v21_completed': new['COMPLETED'],
            'v2_ALL_YAW_REJECTED': old['ALGORITHM_FAILURE'], 'v21_ALL_YAW_REJECTED': new['ALGORITHM_FAILURE'],
            'failure_count_delta_v21_minus_v2': new['ALGORITHM_FAILURE']-old['ALGORITHM_FAILURE'],
            'v2_missing': old['MISSING'], 'v21_missing': new['MISSING'],
            'interpretation': 'REPORTED_NON_DIRECTIONAL'})
    return output


def _joint(labels, *, nondirectional=False):
    if not labels or any(label == 'INCOMPLETE' for label in labels):
        return 'INCOMPLETE'
    if nondirectional:
        return 'REPORTED_NON_DIRECTIONAL'
    if all(label == 'SUPPORTED' for label in labels):
        return 'SUPPORTED'
    if any(label == 'SUPPORTED' for label in labels):
        return 'PARTIALLY_SUPPORTED'
    if all(label == 'UNCHANGED' for label in labels):
        return 'UNCHANGED'
    return 'NOT_SUPPORTED'


def hypothesis_tables(old_rows, new_rows, contract, addendum_contract, *, cases=None):
    """Report every preregistered component, retaining incomplete outcomes."""
    profiles = contract['scope_and_accounting']['profiles']
    indices = [{row_key(r): r for r in rows} for rows in (old_rows, new_rows)]
    components = []
    sequence_cases = {dataset: {r['case_id'] for r in [*old_rows, *new_rows]
                               if r.get('dataset_id', 'BY2') == dataset and (dataset != 'BY2' or r['case_id'] == C00)} for dataset in DATASETS}
    def clean_pair(version, dataset, method):
        ids = sequence_cases[dataset]
        if len(ids) > 1:
            raise ValueError('Multiple natural cases for '+dataset)
        case_id = next(iter(ids), 'UNAVAILABLE_'+dataset)
        key = version, dataset, case_id, method
        return key, *(index.get(key) for index in indices)
    def values(old, new, metric):
        return (_finite(old.get(metric)) if _success(old) else None,
                _finite(new.get(metric)) if _success(new) else None)
    for version in VERSIONS:
        for method in profiles:
            for dataset in DATASETS:
                key, old, new = clean_pair(version, dataset, method)
                identity = {'evaluator_version': version, 'method_id': method, 'dataset_id': dataset, 'case_id': key[2], 'scope': 'CLEAN_SEQUENCE'}
                a, b = values(old, new, 'yaw_abs_error_over_std_median')
                label = 'INCOMPLETE' if a is None or b is None else 'SUPPORTED' if 1 <= b <= 2 and b < a else 'NOT_SUPPORTED'
                components.append({**identity, 'hypothesis': 'H7', 'metric_name': 'yaw_abs_error_over_std_median',
                    'v2_value': a, 'v21_value': b, 'v21_minus_v2': b-a if a is not None and b is not None else None,
                    'decision': label, 'definition': contract['hypotheses']['H7']['definition']})
                counts = {name: values(old, new, name) for name in ('yaw_DOWNWEIGHT', 'yaw_REJECT', 'yaw_DOWNWEIGHT_plus_REJECT')}
                a, b = counts['yaw_DOWNWEIGHT_plus_REJECT']
                label = 'INCOMPLETE' if a is None or b is None else 'SUPPORTED' if b < a else 'UNCHANGED' if b == a else 'NOT_SUPPORTED'
                components.append({**identity, 'hypothesis': 'H8', 'metric_name': 'yaw_DOWNWEIGHT_plus_REJECT',
                    'v2_value': a, 'v21_value': b, 'v21_minus_v2': b-a if a is not None and b is not None else None,
                    'v2_yaw_DOWNWEIGHT': counts['yaw_DOWNWEIGHT'][0], 'v21_yaw_DOWNWEIGHT': counts['yaw_DOWNWEIGHT'][1],
                    'v2_yaw_REJECT': counts['yaw_REJECT'][0], 'v21_yaw_REJECT': counts['yaw_REJECT'][1], 'decision': label})
                for metric in ('roll_rmse_deg', 'pitch_rmse_deg'):
                    a, b = values(old, new, metric)
                    label = 'INCOMPLETE' if a is None or b is None else 'SUPPORTED' if b < a else 'UNCHANGED' if b == a else 'NOT_SUPPORTED'
                    row = {**identity, 'hypothesis': 'H10', 'metric_name': metric, 'v2_value': a, 'v21_value': b,
                           'v21_minus_v2': b-a if a is not None and b is not None else None, 'decision': label}
                    components.append(row)
                    if dataset == 'BY2':
                        components.append({**row, 'scope': 'C00', 'sequence_C00_alias': True})
            a2 = [c for c in addendum_contract['case_rows'] if c['case_family'] == 'A2' and float(c['duration_s']) == 20]
            if len(a2) != 9 or len({c['seed_index'] for c in a2}) != 9:
                raise ValueError('H9 requires the nine preregistered A2 20s seeds')
            for case in a2:
                key = version, 'BY2', case['case_id'], method
                new = indices[1].get(key)
                value = _finite(new.get('outage_end_horizontal_error_m')) if _success(new) else None
                components.append({'hypothesis': 'H9', 'evaluator_version': version, 'method_id': method, 'dataset_id': 'BY2',
                    'case_id': case['case_id'], 'scope': 'A2_20s', 'duration_s': 20, 'seed_id': case['seed_index'],
                    'metric_name': 'outage_end_horizontal_error_m', 'v21_value': value,
                    'threshold_m': contract['hypotheses']['H9']['threshold_m'],
                    'decision': 'INCOMPLETE' if value is None else 'SUPPORTED' if value < contract['hypotheses']['H9']['threshold_m'] else 'NOT_SUPPORTED'})
    for key in sorted(set(indices[0]) | set(indices[1])):
        if key[3] not in profiles:
            continue
        old, new = (index.get(key) for index in indices)
        a, b = values(old, new, 'yaw_rmse_deg')
        meta = new or old
        components.append({'hypothesis': 'H11', 'evaluator_version': key[0], 'method_id': key[3], 'dataset_id': key[1],
            'case_id': key[2], 'scope': _domain(meta), 'case_family': meta.get('case_family'),
            'metric_name': 'yaw_rmse_deg', 'v2_value': a, 'v21_value': b,
            'v21_minus_v2': b-a if a is not None and b is not None else None,
            'direction': 'NOT_PRESET', 'decision': 'INCOMPLETE' if a is None or b is None else 'REPORTED_NON_DIRECTIONAL'})
    summaries = []
    for version in VERSIONS:
        for method in profiles:
            for hypothesis in ('H7', 'H8', 'H9', 'H10', 'H11'):
                rows = [r for r in components if r['evaluator_version'] == version and r['method_id'] == method and r['hypothesis'] == hypothesis]
                labels = [r['decision'] for r in rows]
                summaries.append({'evaluator_version': version, 'method_id': method, 'hypothesis': hypothesis,
                                  'component_count': len(rows), 'component_decisions': dict(Counter(labels)),
                                  'decision': _joint(labels, nondirectional=hypothesis == 'H11'),
                                  'decision_rule_and_Outcome_changed': False})
    return components, summaries


def _failure_tables(records):
    counts = Counter((r.get('case_family'), r.get('degradation_type_id', r.get('degradation_id')), r['method_id'], r['terminal_status']) for r in records)
    failures = [{'case_family': f, 'degradation_id': d, 'method_id': m, 'terminal_status': status, 'run_count': n}
                for (f, d, m, status), n in sorted(counts.items(), key=str)]
    families = {(r.get('case_family'), r.get('degradation_type_id', r.get('degradation_id'))) for r in records}
    yaw = Counter((r.get('case_family'), r.get('degradation_type_id', r.get('degradation_id'))) for r in records if r['terminal_status'] == ALGORITHM_FAILURE)
    return failures, [{'case_family': f, 'degradation_id': d, 'run_count': yaw[(f, d)]} for f, d in sorted(families, key=str)]


def core_tables(unique, records, *, n_boot=10000, seed=20260904, timing=None):
    """Frozen Canonical formulas, without the old aggregate's implicit v1 opens."""
    logical = v2.logical_rows(unique)
    nu, nl = _metrics(unique), _metrics(logical)
    tables = {'UNIQUE_EVALUATION_RESULTS.csv': unique, 'LOGICAL_EVALUATION_RESULTS.csv': logical}
    for filename, rows, groups, metrics in (
        ('UNIQUE_METHOD_SUMMARY.csv', unique, ('method_id', 'effective_configuration_id'), nu),
        ('LOGICAL_METHOD_SUMMARY.csv', logical, ('method_id', 'effective_configuration_id'), nl),
        ('CASE_SUMMARY.csv', logical, ('case_id',), nl),
        ('DEGRADATION_TYPE_SUMMARY.csv', logical, ('degradation_id', 'method_id'), nl),
        ('FAMILY_SUMMARY.csv', logical, ('case_family', 'method_id'), nl)):
        tables[filename] = canonical._summary_rows(rows, groups, metrics)
    pc, ps, ss, fc, fs = v2.pairwise_tables(logical, n_boot=n_boot, seed=seed)
    tables.update({'PAIRWISE_CASE_LEVEL.csv': pc, 'PAIRWISE_SUMMARY.csv': ps, 'SEED_SUMMARY.csv': ss,
                   'FAILURE_AWARE_PAIRWISE_CASE_LEVEL.csv': fc, 'FAILURE_AWARE_PAIRWISE_SUMMARY.csv': fs})
    recovery = [k for k in nl if k.startswith(('pre_', 'during_', 'post_', 'fault_window_')) or k == 'recovery_time_sec']
    tables['RECOVERY_SUMMARY.csv'] = canonical._summary_rows([r for r in logical if r.get('degradation_id') in ('D58', 'D60')], ('degradation_id', 'method_id'), recovery)
    uncertainty = [k for k in nl if any(s in k for s in ('coverage_1sigma', 'coverage_2sigma', 'coverage_3sigma', 'z_rmse', 'calibration_ratio', 'abs_error_sigma_pearson', 'abs_error_sigma_spearman', 'diagonal_normalized_squared_error'))]
    tables['UNCERTAINTY_CALIBRATION_SUMMARY.csv'] = []
    for dimension in ('method_id', 'case_family', 'degradation_id', 'seed_id'):
        for row in canonical._summary_rows(logical, (dimension,), uncertainty):
            row.update(group_dimension=dimension, group_value=row.pop(dimension))
            tables['UNCERTAINTY_CALIBRATION_SUMMARY.csv'].append(row)
    modules = [k for k in nl if k in canonical.MODULE_SCALARS or k == 'source_aware_touch_rate']
    tables['MODULE_ACTION_SUMMARY.csv'] = canonical._summary_rows(logical, ('method_id', 'case_family'), modules)
    tables['RUNTIME_SUMMARY.csv'] = []
    for groups in (('method_id',), ('case_family',), ('method_id', 'case_family')):
        tables['RUNTIME_SUMMARY.csv'].extend(canonical._summary_rows(unique, groups, ('solver_runtime_seconds', 'evaluation_runtime_seconds')))
    tables['RUNTIME_SUMMARY.csv'].append({'method_id': 'ALL', 'case_family': 'ALL', 'metric_name': 'total_wall_time_seconds', 'count': len(records), 'mean': (timing or {}).get('total_wall_time_seconds'), **(timing or {})})
    tables['METRIC_COVERAGE_REPORT.csv'] = canonical._coverage_report(unique)
    tables['FAILURE_COUNTS_BY_FAMILY_CONFIG.csv'], tables['ALL_YAW_REJECTED_BY_FAMILY.csv'] = _failure_tables(records)
    tables['C00_FULL_ABLATION_ANCHORS.csv'] = [r for r in unique if r['case_id'] == C00]
    tables['KEY_PAIRWISE_SUMMARY.csv'] = [r for r in ps if r['scope'] == 'overall']
    return tables


def sequence_tables(rows, *, segment_rows=()):
    """Frozen single-case formulas: three datasets separate, 11 profile rows."""
    logical, pair_cases, pair_summary = [], [], []
    for dataset in DATASETS:
        selected = [r for r in rows if r['dataset_id'] == dataset]
        aliases = v2.logical_rows(selected)
        logical.extend(aliases)
        pc, ps = sequence.pairwise_rows(aliases)
        pair_cases.extend({**r, 'dataset_id': dataset} for r in pc)
        pair_summary.extend({**r, 'dataset_id': dataset} for r in ps)
    metrics = _metrics(rows)
    tables = {'UNIQUE_EVALUATION_RESULTS.csv': rows, 'LOGICAL_EVALUATION_RESULTS.csv': logical,
              'PAIRWISE_CASE_LEVEL.csv': pair_cases, 'PAIRWISE_SUMMARY.csv': pair_summary,
              'WINDOW_SEGMENT_SUMMARY.csv': list(segment_rows),
              'METRIC_COVERAGE_REPORT.csv': canonical._coverage_report(rows)}
    for name, source in (('UNIQUE', rows), ('LOGICAL', logical)):
        tables[name+'_METHOD_SUMMARY.csv'] = canonical._summary_rows(source, ('dataset_id', 'method_id'), metrics)
    tables['MODULE_ACTION_SUMMARY.csv'] = canonical._summary_rows(logical, ('dataset_id', 'method_id'), [m for m in metrics if m in canonical.MODULE_SCALARS])
    tables['RUNTIME_SUMMARY.csv'] = canonical._summary_rows(rows, ('dataset_id', 'method_id'), ('solver_runtime_seconds', 'evaluation_runtime_seconds'))
    return tables


def _segment_coverage(rows):
    expected = {(dataset, method, segment, metric[0]) for dataset in DATASETS
                for method in ('F01', 'F02', 'F03', 'F04', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09')
                for segment in (('pre', 'during', 'post', 'outside', 'full') if dataset == 'BY2O' else ('full',))
                for metric in sequence.SEGMENT_METRICS}
    actual = [(r['dataset_id'], r['method_id'], r['segment_id'], r['metric_name']) for r in rows]
    if len(actual) != len(set(actual)) or set(actual)-expected:
        raise ValueError('Sequence segment identities duplicate or exceed frozen definitions')
    missing = sorted(expected-set(actual))
    return {'status': 'COMPLETE' if not missing else 'INCOMPLETE', 'expected_rows': len(expected),
            'supplied_rows': len(rows), 'missing_rows': len(missing), 'missing_identities': missing,
            'policy': 'Only supplied frozen-definition segment statistics; no fabricated unavailable measurement values'}


def _coverage(expected, rows, label):
    actual = {row_key(r) for r in rows}
    if len(actual) != len(rows) or actual != expected:
        raise ValueError(label+' identity coverage differs: missing='+str(len(expected-actual))+' extra='+str(len(actual-expected)))


def aggregate_all(evaluations, records, v21_contract, v2_contract, addendum_contract,
                  output_root, code_commit, *, baseline_evaluations, baseline_records,
                  case_rows, consistency_rows=(), baseline_consistency_rows=(),
                  segment_rows=(), timing=None, n_boot=None):
    """Write all three domains and machine F-report tables beneath owned root.

    Inputs are lists of actual sealed index rows supplied by the controller.
    Baselines cover v2 core, addendum and 3 natural sequences (BY2 C00 once).
    New rows contain ten profiles; old F01 rows are reused as formal records.
    H7 supplements must contain its exact frozen P05 metric, not another ratio.
    """
    root = Path(output_root)
    if not root.is_absolute() or '..' in root.parts or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Aggregation requires absolute non-symlink output')
    if any((root/name).exists() for name in ('13_AGGREGATE', '13_AGGREGATE_ADDENDUM', '13_AGGREGATE_SEQUENCES', 'P13_MACHINE_REPORT')):
        raise FileExistsError('Aggregate output exists; preserve exclusive prior outputs')
    profiles = v21_contract['scope_and_accounting']['profiles']
    all_methods = ['F01', *profiles]
    cases = {r['case_id']: dict(r) for r in case_rows}
    if len(cases) != 541 or C00 not in cases:
        raise ValueError('Exact frozen 541 core case rows required')
    cases.update({r['case_id']: dict(r) for r in addendum_contract['case_rows']})
    if len(cases) != 586:
        raise ValueError('Core plus addendum case identity must close to 586')
    sequence_keys = [(dataset, spec['case_id']) for dataset, spec in v2_contract['sequences'].items() if dataset != 'BY2']
    base_keys = [('BY2', case_id) for case_id in cases]+sequence_keys
    expected_new = {(version, dataset, case_id, method) for version in VERSIONS for dataset, case_id in base_keys for method in profiles}
    expected_full = {(version, dataset, case_id, method) for version in VERSIONS for dataset, case_id in base_keys for method in all_methods}
    new = normalize_rows(evaluations, supplements=consistency_rows, cases=cases)
    old = normalize_rows(baseline_evaluations, supplements=baseline_consistency_rows, cases=cases)
    _coverage(expected_new, new, 'New evaluation')
    _coverage(expected_full, old, 'Frozen baseline evaluation')
    native_expected = {(d, c, m) for _, d, c, m in expected_new}
    native_keys = {(r.get('dataset_id', 'BY2'), r['case_id'], r['method_id']) for r in records}
    if len(records) != len(native_keys) or native_keys != native_expected:
        raise ValueError('New native terminal coverage differs from preregistration')
    old_f01 = [dict(r, formal_F01_reused=True) for r in old if r['method_id'] == 'F01']
    formal = [*new, *old_f01]
    _coverage(expected_full, formal, 'Formal v2.1 including unchanged F01')
    native = [copy.deepcopy(r) for r in records]+[dict(r, formal_F01_reused=True) for r in baseline_records if r['method_id'] == 'F01']
    expected_native_full = {(d, c, m) for _, d, c, m in expected_full}
    if len(native) != len(expected_native_full) or {(r.get('dataset_id', 'BY2'), r['case_id'], r['method_id']) for r in native} != expected_native_full:
        raise ValueError('Formal native F01 reuse coverage differs')
    for row in native:
        if row['terminal_status'] not in ('COMPLETED', ALGORITHM_FAILURE):
            raise ScientificStop('NATIVE_UNREGISTERED_FAILURE', 'Aggregate received unsupported native terminal')
        meta = cases.get(row['case_id'], {})
        row.setdefault('case_family', meta.get('case_family', 'natural_sequence'))
        row.setdefault('degradation_type_id', meta.get('degradation_type_id', 'CLEAN'))
    bootstrap = 10000 if n_boot is None else n_boot
    if bootstrap != 10000 and not all(str(r.get('synthetic_data_used')).lower() == 'true' for r in records):
        raise ValueError('Bootstrap override allowed only for explicit synthetic fixtures')
    root.mkdir(parents=True, exist_ok=True)
    statuses = []
    for version in VERSIONS:
        current = [r for r in formal if r['evaluator_version'] == version]
        core = [r for r in current if r['domain'] == 'CORE']
        core_native = [r for r in native if _domain(r) == 'CORE']
        clean = [r for r in current if r['domain'] == 'SEQUENCE' or r['case_id'] == C00]
        tables = core_tables(core, core_native, n_boot=bootstrap, timing=timing)
        tables['SEQUENCE_CONSISTENCY_EVALUATION.csv'] = clean
        destination = root/'13_AGGREGATE'/version
        destination.mkdir(parents=True, exist_ok=False)
        for name, rows in tables.items():
            v2.write_csv(destination/name, rows)
        status = {'terminal_status': 'PASS_CANONICAL541_V21_AGGREGATED_WITH_EXPLICIT_TERMINALS',
                  'protocol_id': 'SENSOR_MODEL_V2_1', 'code_commit': code_commit, 'evaluator_version': version,
                  'unique_evaluated': len(core), 'logical_evaluated': len(tables['LOGICAL_EVALUATION_RESULTS.csv']),
                  'evaluation_status_counts': dict(Counter(r['evaluation_status'] for r in core)),
                  'F01_formal_reused_rows': sum(r['method_id'] == 'F01' for r in core),
                  'data_mode': 'controlled_degradation_matrix_with_real_C00_reference', 'synthetic_data_used': False,
                  'semisynthetic_data_used': True, 'trace_used_online': False, 'plotting_executed': False}
        for name in ('FINAL_EVALUATION_SUMMARY.json', 'EVALUATION_AND_AGGREGATE_STATUS.json'):
            write_json(destination/name, status)
        seqroot = root/'13_AGGREGATE_SEQUENCES'/version
        seqroot.mkdir(parents=True, exist_ok=False)
        segments = [r for r in segment_rows if _version(r) == version]
        segment_coverage = _segment_coverage(segments)
        for name, rows in sequence_tables(clean, segment_rows=segments).items():
            v2.write_csv(seqroot/name, rows)
        seqstatus = {'terminal_status': 'PASS_THREE_SEQUENCE_V21_AGGREGATE' if segment_coverage['status'] == 'COMPLETE' else 'PARTIAL_THREE_SEQUENCE_V21_SEGMENTS_UNAVAILABLE', 'unique_rows': len(clean),
                     'logical_rows': 39, 'evaluator_version': version, 'code_commit': code_commit,
                     'data_mode': 'real', 'synthetic_data_used': False, 'semisynthetic_data_used': False,
                     'window_segment_coverage': segment_coverage,
                     'single_case_inference': 'NOT_AVAILABLE_SINGLE_CASE'}
        write_json(seqroot/'FINAL_EVALUATION_SUMMARY.json', seqstatus)
        write_json(seqroot/'FIELD_DEFINITIONS.json', {'base': sequence.field_definitions(), 'protocol': 'v2.1',
            'profile_registry_count': 11, 'logical_alias_count': 2, 'counter_aliases': canonical.MODULE_SCALARS,
            'H7_metric': 'yaw_abs_error_over_std_median; missing stays UNAVAILABLE; no substitute ratio'})
        statuses.append(status)
    addendum.aggregate_all([r for r in formal if r['domain'] == 'ADDENDUM'],
                           [r for r in native if _domain(r) == 'ADDENDUM'], addendum_contract, root, code_commit, n_boot=bootstrap)
    reportroot = root/'P13_MACHINE_REPORT'
    reportroot.mkdir(exist_ok=False)
    comparison = comparison_tables(old, formal, profiles, cases=cases)
    failures = failure_comparison(old, formal, profiles, cases=cases)
    components, decisions = hypothesis_tables(old, formal, v21_contract, addendum_contract, cases=cases)
    v2.write_csv(reportroot/'V2_V21_COMPARISON.csv', comparison)
    v2.write_csv(reportroot/'FAILURE_COUNTS_V2_V21_BY_FAMILY_CONFIG.csv', failures)
    v2.write_csv(reportroot/'H7_H11_COMPONENT_DECISIONS.csv', components)
    v2.write_csv(reportroot/'H7_H11_PROFILE_DECISIONS.csv', decisions)
    v2.write_csv(reportroot/'CONSISTENCY_RATIOS_V2_V21.csv', [r for r in components if r['hypothesis'] == 'H7'])
    focus = [r for r in comparison if r['scope'] == 'CASE' or r['degradation_id'] in ('D05', 'D06', 'D61', 'D62')]
    v2.write_csv(reportroot/'F_REPORT_TEN_PROFILE_CHANGES.csv', focus)
    for version in VERSIONS:
        v2.write_csv(root/'13_AGGREGATE'/version/'V2_V21_COMPARISON.csv', [r for r in comparison if r['evaluator_version'] == version])
    summary = {'status': 'PASS_V21_AGGREGATION_WITH_EXPLICIT_HYPOTHESIS_AVAILABILITY',
               'new_native_records': len(records), 'new_evaluation_terminal_rows': len(new),
               'formal_native_records_with_F01': len(native), 'formal_evaluation_rows_with_F01': len(formal),
               'F01_reused_evaluation_rows': len(old_f01), 'source_index_hashes': {
                   'new_evaluations': _hash_rows(evaluations), 'new_native': _hash_rows(records),
                   'baseline_evaluations': _hash_rows(baseline_evaluations), 'baseline_native': _hash_rows(baseline_records)},
               'hypothesis_decisions': decisions, 'decision_rule_and_Outcome_changed': False,
               'code_commit': code_commit, 'sensor_model_group_hash': v21_contract['sensor_model_group_hash'],
               'epoch_metric_recomputation': False, 'summary_statistics_recomputed_from_supplied_rows': True,
               'evaluator_calls': 0, 'trace_reads': 0}
    write_json(reportroot/'AGGREGATION_SUMMARY.json', summary)
    seal = {p.relative_to(root).as_posix(): sha256_file(p) for folder in (
        '13_AGGREGATE', '13_AGGREGATE_ADDENDUM', '13_AGGREGATE_SEQUENCES', 'P13_MACHINE_REPORT')
        for p in sorted((root/folder).rglob('*')) if p.is_file()}
    write_json(reportroot/'AGGREGATE_SEAL.json', {'status': 'SEALED', 'files_sha256': seal, 'code_commit': code_commit})
    return summary
