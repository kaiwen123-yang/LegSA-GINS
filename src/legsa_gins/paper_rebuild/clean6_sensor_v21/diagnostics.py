"""Post-evaluation P13 sidecars using the original P05/CLEAN5 definitions.

No solver, evaluator, provider or raw reference is opened here. Call
``write_run_sidecars`` before archiving a completed native/evaluation pair.
The original evaluator rows/files remain untouched; enriched copies are
returned for aggregation. ``old_h7_rows`` consumes already verified v2 indices
and never reconstructs STD from calibration ratios or interpolated 3-sigma.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_parity.evaluation import body_frame_bias, full_window_segments, _csv
from ..clean5_parity_p05.evaluation import consistency
from ..clean5_sequence.evaluation_tables import segment_rows
from ..manifest import sha256_file

DATASETS = ('BY2', 'BY2H', 'BY2O')
PROFILES = ('F02', 'F03', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09', 'F04')
AXES = ('height', 'north', 'east', 'yaw')
C00 = 'C00_clean_normal'
DEFINITION = 'clean5_parity_p05.evaluation.consistency (unchanged)'
RATIO_FIELDS = tuple(axis + '_abs_error_over_std_median' for axis in AXES)
IDENTITY = ('run_id', 'method_id', 'effective_configuration_id', 'dataset_id',
            'case_id', 'variant_id', 'evaluator_contract', 'evaluator_version',
            'code_commit', 'data_mode', 'synthetic_data_used',
            'semisynthetic_data_used', 'source_row')


def _regular(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unsafe diagnostic source/target path: ' + str(path))
    return path


def _pin(path, expected=None):
    path = _regular(path)
    digest = sha256_file(path)
    if expected is not None and digest != expected:
        raise ValueError('Diagnostic source hash differs: ' + str(path))
    return {'path': str(path), 'sha256': digest, 'size_bytes': path.stat().st_size}


def _version(row):
    version = row.get('evaluator_version', row.get('evaluator_contract', '').removeprefix('evaluator_contract_'))
    if version not in ('v2', 'v3'):
        raise ValueError('Diagnostic evaluator version must be v2 or v3')
    return version


def _identity(record, row):
    for key in ('run_id', 'method_id', 'dataset_id', 'case_id'):
        if record.get(key) != row.get(key):
            raise ValueError('Diagnostic run/evaluation identity differs: ' + key)
    version = _version(row)
    identity = {key: row.get(key, record.get(key)) for key in IDENTITY}
    identity.update(evaluator_version=version, evaluator_contract='evaluator_contract_' + version,
                    effective_configuration_id=row.get('effective_configuration_id', record.get('effective_profile')),
                    trace_used_online=False, diagnostic_definition=DEFINITION,
                    consistency_status='SAME_POINT_STD' if version == 'v2' else 'ORIGINAL_IMU_STD_DIAGNOSTIC_ONLY',
                    v3_std_transport='NOT_APPLICABLE' if version == 'v2' else 'UNTRANSPORTED_STD_DIAGNOSTIC_ONLY',
                    yaw_consistency_status='UNCHANGED_YAW_STATE_STD',
                    full_covariance_nees=False, evaluator_reinvoked=False,
                    epoch_deleted_for_metric=False, output_only_correction=False)
    return identity


def consistency_rows(values, identity):
    """Project all four original ratios and their original validity counters."""
    rows = []
    for axis in AXES:
        metric = axis + '_abs_error_over_std_median'
        value = values.get(metric, 'UNAVAILABLE')
        rows.append({**identity, 'axis': axis, 'metric_name': metric, 'value': value,
                     'unit': 'dimensionless',
                     'status': 'AVAILABLE' if isinstance(value, (int, float)) else 'UNAVAILABLE',
                     **{axis + suffix: values.get(axis + suffix) for suffix in (
                         '_consistency_total_count', '_consistency_valid_count',
                         '_std_nonfinite_count', '_std_nonpositive_count', '_error_nonfinite_count')}})
    return rows


def sidecars_from_arrays(record, row, errors, std, nav):
    """Pure original-definition statistics; suitable for synthetic unit tests.

    STD columns: time=0, N/E/U=1/2/3, yaw=9. NAV time=1, yaw=10.
    Errors are the completed evaluator's original (possibly v3) error frame.
    """
    if record.get('terminal_status') != 'COMPLETED' or row.get('evaluation_status') != 'COMPLETED':
        raise ValueError('Diagnostics require completed native and evaluator output')
    if record.get('dataset_id') not in DATASETS:
        raise ValueError('Only the three registered sequences are supported')
    identity = _identity(record, row)
    std, nav = np.asarray(std, float), np.asarray(nav, float)
    required = ('time', 'err_n_m', 'err_e_m', 'err_u_m', 'horizontal_err_m',
                'position_3d_err_m', 'yaw_err_deg')
    if not set(required) <= set(errors.columns) or not len(errors):
        raise ValueError('Original evaluator error fields/support are incomplete')
    values = errors[list(required)].to_numpy(float)
    if not np.isfinite(values).all() or np.any(np.diff(values[:, 0]) <= 0):
        raise ValueError('Nonfinite or nonmonotonic original evaluator errors')
    if (std.ndim != 2 or std.shape[1] < 10 or not len(std) or
            not np.isfinite(std[:, 0]).all() or nav.ndim != 2 or nav.shape[1] < 11 or not len(nav)):
        raise ValueError('Incomplete native STD/NAV shape or time support')
    # The original definition reports invalid denominators as UNAVAILABLE;
    # the native/evaluator scientific gate is responsible for nonfinite STD.
    ratios = consistency(errors, std)
    enriched = {**row, **ratios, **identity}
    window = list(map(float, record['window']))
    if len(window) != 2 or not np.isfinite(window).all() or window[0] >= window[1]:
        raise ValueError('Invalid frozen sequence window')
    if values[0, 0] < window[0] or values[-1, 0] > window[1]:
        raise ValueError('Evaluator errors exceed the frozen sequence window')
    if record['dataset_id'] == 'BY2':
        if window != [66., 340.]:
            raise ValueError('Original BY2 segment definition requires [66, 340]')
        segments = full_window_segments([enriched])
    else:
        segments = segment_rows(errors, registry=record, dataset_id=record['dataset_id'],
            window={'t_start': window[0], 't_end': window[1]}, case_meta=record['case_meta'])
    return {'evaluation': enriched,
            'consistency_rows': consistency_rows(ratios, identity),
            'segment_rows': [{**item, 'evaluator_contract': identity['evaluator_contract'],
                              'evaluator_version': identity['evaluator_version']} for item in segments],
            'body_rows': [{**identity, **body_frame_bias(errors, nav), 'status': 'AVAILABLE'}]}


def _error_path(row):
    source = _regular(row['error_series_source'])
    candidates = [source]
    if source.name == 'error_series.csv.gz':
        candidates.append(source.with_suffix(''))
    elif source.name == 'error_series.csv':
        candidates.append(Path(str(source) + '.gz'))
    elif source.is_dir():
        candidates = [source / 'error_series.csv', source / 'error_series.csv.gz']
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise FileNotFoundError('Completed evaluator original error series is absent')
    # Canonical reads plain first when both forms exist. Never silently select
    # a contradictory duplicate: compare the decompressed CSV bytes.
    if len(existing) > 1 and len({_uncompressed_hash(path) for path in existing}) != 1:
        raise ValueError('Plain and compressed original error series disagree')
    return existing[0]


def _uncompressed_hash(path):
    digest = hashlib.sha256()
    opener = gzip.open if Path(path).suffix == '.gz' else open
    with opener(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _write_once(target, payload):
    target = _regular(target)
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if target.exists():
        if target.read_text() != text:
            raise ValueError('Immutable diagnostic sidecar differs: ' + str(target))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as stream:
            stream.write(text)


def _csv_once(path, values):
    if not path.exists():
        _csv(path, values)
        return
    fields = list(dict.fromkeys(key for row in values for key in row)) or ['status']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows({key: canonical._csv_value(row.get(key)) for key in fields} for row in values)
    if path.read_bytes() != buffer.getvalue().encode():
        raise ValueError('Unpublished diagnostic CSV differs')


def write_run_sidecars(record, evaluation_rows, *, output_root=None):
    """Write per-version sidecars before archive; return enriched row copies.

    Default target: ``evaluation_output_root/P13_DIAGNOSTICS``. When an
    explicit output_root is supplied, append ``version/run_id``. Repeated calls
    reuse verified sidecars and do not recompute metrics. Original evaluator
    JSON/CSV and native outputs are never modified.
    """
    rows = list(evaluation_rows)
    if len({_version(row) for row in rows}) != len(rows):
        raise ValueError('Duplicate diagnostic evaluator version for one run')
    native = _regular(record['output_root'])
    source_pins = {}
    for role, name in (('nav', 'KF_GINS_Navresult.nav'), ('std', 'KF_GINS_STD.txt')):
        source_pins[role] = _pin(native / name, record['output_seal'][name]['sha256'])
    result = {'evaluations': [], 'consistency_rows': [], 'segment_rows': [], 'body_rows': [], 'manifests': []}
    nav = std = None
    for row in rows:
        version = _version(row)
        _identity(record, row)
        if row.get('std_sha256') != source_pins['std']['sha256'] or row.get('native_nav_sha256') != source_pins['nav']['sha256']:
            raise ValueError('Evaluator NAV/STD hashes differ from native seal')
        error_path = _error_path(row)
        pins = {**source_pins, 'error_series': _pin(error_path)}
        row_hash = hashlib.sha256(json.dumps(row, sort_keys=True, allow_nan=False).encode()).hexdigest()
        target = (_regular(row['evaluation_output_root']) / 'P13_DIAGNOSTICS' if output_root is None
                  else _regular(output_root) / version / record['run_id'])
        target = _regular(target)
        manifest_path = target / 'DIAGNOSTIC_MANIFEST.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if (manifest['source_pins'] != pins or manifest['status'] != 'PASS' or
                    manifest['input_evaluation_row_sha256'] != row_hash):
                raise ValueError('Existing diagnostic source identity differs')
            for relative, pin in manifest['files'].items():
                _pin(target / relative, pin['sha256'])
            payload = json.loads((target / 'DIAGNOSTIC_ROWS.json').read_text())
            if payload['evaluation']['source_row'] != row['source_row']:
                raise ValueError('Existing diagnostics belong to a different evaluator row')
        else:
            if nav is None:
                nav = canonical._read_numeric_table(Path(source_pins['nav']['path'])).to_numpy(float)
                std = canonical._read_numeric_table(Path(source_pins['std']['path'])).to_numpy(float)
            payload = sidecars_from_arrays(record, row, pd.read_csv(error_path), std, nav)
            payload['evaluation']['diagnostic_sidecar_root'] = str(target)
            payload['evaluation']['h7_diagnostic_status'] = 'AVAILABLE_ORIGINAL_P05_DEFINITION'
            _write_once(target / 'DIAGNOSTIC_ROWS.json', payload)
            tables = {'CONSISTENCY_ROWS.csv': payload['consistency_rows'],
                      'WINDOW_SEGMENT_SUMMARY.csv': payload['segment_rows'],
                      'BODY_FRAME_BIAS.csv': payload['body_rows']}
            for filename, values in tables.items():
                _csv_once(target / filename, values)
            manifest = {'schema_version': 'clean6.sensor_v21.diagnostics.v1', 'status': 'PASS',
                **_identity(record, row), 'source_pins': pins,
                'input_evaluation_row_sha256': row_hash,
                'files': {name: _pin(target / name) for name in ('DIAGNOSTIC_ROWS.json', *tables)},
                'consistency_definition': DEFINITION,
                'segment_definition': 'clean5_parity.full_window_segments / clean5_sequence.segment_rows unchanged',
                'body_definition': 'clean5_parity.evaluation.body_frame_bias unchanged; original NAV yaw; ddof=0',
                'scalar_substitution_used': False, 'frozen_evaluator_changed': False}
            _write_once(manifest_path, manifest)
        result['evaluations'].append(payload['evaluation'])
        for name in ('consistency_rows', 'segment_rows', 'body_rows'):
            result[name].extend(payload[name])
        result['manifests'].append(_pin(manifest_path))
    return result


def _natural(row):
    return row.get('dataset_id', 'BY2') in DATASETS and (row.get('dataset_id', 'BY2') != 'BY2' or row.get('case_id') == C00)


def _key(row):
    return row.get('dataset_id', 'BY2'), row['case_id'], row['method_id']


def old_h7_rows(records, evaluation_rows, *, calibrated_root, profiles=PROFILES):
    """Compute exact old ratios only from full STD matching the v2 seal.

    Inputs are the hash-verified original indices returned by the P13 aggregate
    baseline loader. Retained native STD is preferred; the exact P06 full STD
    is eligible only after SHA equality with the v2 full-file seal. Missing STD
    gives INCOMPLETE. Errors are the v2 run's own hash-verified archived CSV;
    P06 aggregate scalars and the frozen evaluator's interpolated 3-sigma
    columns never substitute for these original P05 inputs.
    """
    selected = [r for r in records if _natural(r) and r['method_id'] in profiles]
    index = {_key(row): row for row in selected}
    if len(index) != len(selected):
        raise ValueError('Duplicate natural-sequence v2 native identity')
    rows = [r for r in evaluation_rows if _natural(r) and r['method_id'] in profiles]
    if len({(_key(row), _version(row)) for row in rows}) != len(rows):
        raise ValueError('Duplicate natural-sequence v2 evaluation identity')
    result = {'evaluations': [], 'consistency_rows': [], 'missing': [], 'source_pins': []}
    cached = {}
    for row in rows:
        key, version = _key(row), _version(row)
        record = index[key]
        identity = _identity(record, row)
        enriched = dict(row)
        if key not in cached:
            receipt_path = _regular(record['archive_receipt'])
            receipt = json.loads(receipt_path.read_text())
            if receipt.get('status') != 'ARCHIVE_VERIFIED':
                raise ValueError('Old H7 archive was not verified')
            result['source_pins'].append(_pin(receipt_path))
            native_dir = receipt_path.parent / 'solver'
            candidates = [native_dir / 'KF_GINS_STD.txt', native_dir / 'KF_GINS_STD.txt.gz']
            if record['method_id'] in ('F01', 'F02', 'F03', 'A04', 'F04'):
                candidates.append(_regular(calibrated_root) / '03_CALIBRATED_RUNS' /
                    ('CLEAN5_CALIBRATED_' + record['dataset_id'] + '_' + record['method_id']) / 'KF_GINS_STD.txt')
            candidate = next((p for p in candidates if p.is_file()), None)
            native_pin = record['output_seal']['KF_GINS_STD.txt']
            if candidate is not None:
                pin = _pin(candidate)
                if _uncompressed_hash(candidate) != native_pin['sha256']:
                    raise ValueError('Old H7 full STD does not match v2 output seal')
                pin.update(native_uncompressed_sha256=native_pin['sha256'], full_STD_verified_against_v2_seal=True)
                result['source_pins'].append(pin)
                std = canonical._read_numeric_table(candidate).to_numpy(float)
            else:
                pin, std = None, None
            cached[key] = receipt_path.parent, receipt, pin, std, [str(p) for p in candidates]
        archived, receipt, std_pin, std, attempted = cached[key]
        reason = None
        if record.get('terminal_status') != 'COMPLETED' or row.get('evaluation_status') != 'COMPLETED':
            reason = 'ORIGINAL_RUN_OR_EVALUATOR_NOT_COMPLETED'
        elif std is None:
            reason = 'FULL_V2_STD_NOT_RETAINED; no calibration-ratio or interpolated-3sigma substitution'
        if reason is not None:
            enriched.update({field: 'UNAVAILABLE' for field in RATIO_FIELDS})
            enriched.update(h7_reference_status='INCOMPLETE', h7_reference_reason=reason)
            missing = {**identity, 'status': 'INCOMPLETE', 'reason': reason,
                       'attempted_STD_paths': attempted, 'old_solver_rerun': False, 'scalar_substitution_used': False}
            result['missing'].append(missing)
            result['consistency_rows'].extend(consistency_rows(enriched, missing))
        else:
            relative = version + '/FROZEN_EVALUATOR/error_series.csv.gz'
            if relative not in receipt['retained_files']:
                relative = version + '/FROZEN_EVALUATOR/error_series.csv'
            if relative not in receipt['retained_files']:
                raise ValueError('Old completed H7 error series absent from archive receipt')
            error_pin = _pin(archived / relative, receipt['retained_files'][relative]['sha256'])
            result['source_pins'].append(error_pin)
            values = consistency(pd.read_csv(error_pin['path']), std)
            enriched.update(values, h7_reference_status='AVAILABLE_EXACT_V2_FULL_STD',
                h7_reference_definition=DEFINITION, h7_reference_std_pin=std_pin,
                h7_reference_error_pin=error_pin, old_solver_rerun=False, scalar_substitution_used=False)
            result['consistency_rows'].extend(consistency_rows(values, {**identity,
                'h7_reference_status': enriched['h7_reference_status'],
                'full_STD_verified_against_v2_seal': True, 'old_solver_rerun': False}))
        result['evaluations'].append(enriched)
    return result
