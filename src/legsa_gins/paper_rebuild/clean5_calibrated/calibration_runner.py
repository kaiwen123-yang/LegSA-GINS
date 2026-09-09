"""Exclusive, strace-isolated P06 calibration; no solver or evaluator invocation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import numpy as np
import yaml

from ...datasets.by2.go2_body_state_parser import parse_go2_body_state_text
from ..clean5_parity.input_audit import csv_rows, decode_receiver, epoch_key, stamp
from ..clean5_parity.runtime import resolve, write_json
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..clean5_sequence.solver_runner import execution_state
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .calibration import AXES, LAGS_MS, calibrate_arrays

CONTRACT = 'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL_CONTRACT.yaml'
INPUT_ROLES = {'provider_bundle', 'imu_increment', 'gnss_v2', 'a1', 'go2_body', 'pvt_raw', 'status', 'raw_lock'}
FLAGS = {'data_mode': 'real_by2_raw_trace_free_calibration', 'synthetic_data_used': False,
         'semisynthetic_data_used': False, 'trace_used_online': False,
         'receiver_imu_as_body_imu': False, 'final_v23_output_solver_input': False,
         'LegSA_output_solver_input': False, 'per_case_tuning': False,
         'output_only_correction': False, 'epoch_deleted_for_metric': False,
         'old_runtime_input_count': 0, 'solver_invocation_count': 0, 'evaluator_invocation_count': 0}


def dump_csv(path, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    if not columns:
        raise ValueError('Empty calibration table schema')
    with Path(path).open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: 'UNAVAILABLE' if v is None else v for k, v in row.items()})


def forbidden_path(path):
    p = Path(path)
    return p.suffix.lower() in ('.bag', '.fpl') or p.name.lower().startswith('trace_') or p.name.lower() == 'trace.csv'


def strict_open_audit(records, *, raw_root, clean_root, output_root, input_paths):
    """Reject forbidden attempts and every undeclared protected-data read/write."""
    raw_root, clean_root, output_root = map(Path, (raw_root, clean_root, output_root))
    allowed = {Path(p).resolve() for p in input_paths}
    denied, forbidden = [], []
    for row in records:
        paths = [Path(row['path']), Path(row.get('lexical_path', row['path']))]
        if any(forbidden_path(p) for p in paths):
            forbidden.append(row)
        for p in paths:
            protected = p == raw_root or raw_root in p.parents or p == clean_root or clean_root in p.parents
            own = p == output_root or output_root in p.parents
            if protected and not own and p.resolve() not in allowed:
                denied.append(row)
                break
    writes = write_scope_audit(records, raw_root=raw_root, clean_root=clean_root,
                               allowed_write_roots=[output_root])
    counts = {'trace': 0, 'bag': 0, 'fpl': 0}
    for row in forbidden:
        p = Path(row['path'])
        key = p.suffix.lower().lstrip('.') if p.suffix.lower() in ('.bag', '.fpl') else 'trace'
        counts[key] += 1
    return {'pass': not forbidden and not denied and writes['pass'],
            'forbidden_open_counts': counts, 'forbidden_open_records': forbidden,
            'undeclared_protected_open_records': denied, 'write_scope': writes,
            'failed_open_attempts_also_audited': True,
            'input_path_count': len(allowed), 'input_paths': sorted(str(p) for p in allowed)}


def verify_input_pins(spec, registry):
    if set(spec['inputs']) != INPUT_ROLES:
        raise ValueError('Calibration role set differs from preregistration')
    paths = {}
    for role, pin in spec['inputs'].items():
        path = resolve(pin['path'], registry)
        if forbidden_path(path) or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Forbidden or symlink calibration input: '+role)
        if sha256_file(path) != pin['sha256']:
            raise ValueError('Calibration source hash mismatch: '+role)
        paths[role] = path
    lock = {r['relative_path']: r['sha256'] for r in csv_rows(paths['raw_lock'])}
    for role in ('go2_body', 'pvt_raw', 'status'):
        relative = paths[role].relative_to(registry.raw_root).as_posix()
        if lock.get(relative) != spec['inputs'][role]['sha256']:
            raise ValueError('Calibration raw identity absent from immutable lock: '+role)
    bundle = json.loads(paths['provider_bundle'].read_text())
    providers = bundle['variants']['V2s']['providers']
    for key, role in [('imupath', 'imu_increment'), ('gnsspath', 'gnss_v2')]:
        if (Path(providers[key]['path']) != paths[role]
                or providers[key]['sha256'] != spec['inputs'][role]['sha256']):
            raise ValueError('Frozen V2s provider lineage mismatch: '+role)
    if bundle['audit']['s'] != spec['s'] or bundle['audit']['g_local_mps2'] != spec['g_local_mps2']:
        raise ValueError('Frozen V2s scale/gravity identity mismatch')
    return paths


def load_arrays(paths, spec):
    """Only declared observation/provider roles, with source epoch/token checks."""
    base = float(spec['base_time'])
    raw_body = parse_go2_body_state_text(paths['go2_body'])
    # Match parse_sportmodestate_text's finite input projection before dt mapping.
    frame_rows = [r for r in raw_body if r.get('stamp_sec') is not None and r.get('stamp_nanosec') is not None
                  and all(isinstance(r.get(k), (int, float)) and math.isfinite(float(r[k]))
                          for k in ('gyro_x', 'gyro_y', 'gyro_z', 'acc_x', 'acc_y', 'acc_z'))]
    ft = np.asarray([int(r['stamp_sec'])+int(r['stamp_nanosec'])*1e-9 for r in frame_rows])
    measured_dt = np.diff(ft)
    keep = np.flatnonzero((measured_dt > 0) & (measured_dt <= .1))+1
    imu_lines = [line.split() for line in paths['imu_increment'].read_text().splitlines()]
    if len(imu_lines) != len(keep) or any(len(line) != 7 for line in imu_lines):
        raise ValueError('Frozen V2s rows/raw valid interval count mismatch')
    expected_tokens = [format(float(format(ft[k]-base, '.12g')), '.6f') for k in keep]
    if expected_tokens != [r[0] for r in imu_lines]:
        raise ValueError('V2s timestamp tokens differ from frozen current-sample raw map')
    imu = np.asarray(imu_lines, float)
    rp = [r for r in raw_body if all(isinstance(r.get(k), (int, float)) and math.isfinite(float(r[k]))
                                   for k in ('timestamp', 'roll_rad', 'pitch_rad'))]
    status = csv_rows(paths['status'])
    week = {int(float(r['time_gps_wno'])) for r in status}
    if len(week) != 1:
        raise ValueError('Week rollover not authorized')
    gps_week = week.pop()
    utc = lambda k: 315964800+gps_week*604800+k/1000.-18-base
    status_map = {round(stamp(r, 'header.stamp.')*1000): epoch_key(r) for r in status}
    if len(status_map) != len(status):
        raise ValueError('Duplicate status-header millisecond identity')
    a1 = csv_rows(paths['a1'])
    a1_rows = []
    for row in a1:
        key = status_map.get(round(float(row['source_timestamp'])*1000))
        if key is None:
            raise ValueError('Frozen A1 epoch missing from status identity map')
        a1_rows.append((key, utc(key), float(row['body_yaw_ned_deg']), float(row['yaw_std_deg'])))
    if len({r[0] for r in a1_rows}) != len(a1_rows):
        raise ValueError('Duplicate mapped A1 iTOW epoch')
    a1_rows.sort()
    _, pvt = decode_receiver(paths['pvt_raw'])
    pvt_keys = sorted(pvt)
    gnss = np.loadtxt(paths['gnss_v2'], ndmin=2)
    if gnss.shape[1] != 18 or not np.isfinite(gnss).all():
        raise ValueError('Frozen V2 GNSS18 shape/finite failure')
    gnss_map = {round(float(r[0])*1000): r for r in gnss}
    if len(gnss_map) != len(gnss):
        raise ValueError('Duplicate GNSS18 millisecond epoch')
    supported_a1 = [r for r in a1_rows if round(r[1]*1000) in gnss_map]
    if {round(r[1]*1000) for r in supported_a1} != {round(float(r[0])*1000) for r in gnss if r[17] == 1}:
        raise ValueError('A1 versus V2 yaw-valid epoch set mismatch')
    yaw_deltas = []
    for key, t, yaw_deg, yaw_std in supported_a1:
        row = gnss_map[round(t*1000)]
        diff = abs((row[13]-yaw_deg+180)%360-180)
        if diff > 1e-6 or abs(row[14]-yaw_std) > 1e-6:
            raise ValueError('A1 versus frozen GNSS18 serialized yaw/std mismatch')
        yaw_deltas.append(diff)
    for key in pvt_keys:
        row = gnss_map.get(round(utc(key)*1000))
        if row is None or row[16] != 1 or not np.allclose(row[7:10], pvt[key]['velocity_mps'], rtol=0, atol=1e-12):
            raise ValueError('Same-iTOW PVT velocity versus frozen V2 RV mismatch')
    arrays = dict(imu_times_s=imu[:, 0], imu_dvel_mps=imu[:, 4:7], imu_dt_s=measured_dt[keep-1],
                  rpy_times_s=np.asarray([float(r['timestamp'])-base for r in rp]),
                  roll_pitch_rad=np.asarray([[r['roll_rad'], r['pitch_rad']] for r in rp]),
                  a1_times_s=np.asarray([r[1] for r in a1_rows]), yaw_rad=np.deg2rad([r[2] for r in a1_rows]),
                  pvt_itow_ms=np.asarray(pvt_keys, dtype=np.int64),
                  pvt_times_s=np.asarray([utc(k) for k in pvt_keys]),
                  pvt_velocity_mps=np.asarray([pvt[k]['velocity_mps'] for k in pvt_keys]),
                  window=spec['window_seconds'], g_local_mps2=spec['g_local_mps2'],
                  frozen_vrw=spec['frozen_vrw'], frozen_abstd=spec['frozen_abstd'],
                  lags_ms=spec['fit']['lag_milliseconds'], max_heading_gap_s=spec['orientation']['maximum_a1_gap_seconds'])
    audit = {'raw_body_frame_count': len(raw_body), 'imu_provider_row_count': len(imu),
             'frozen_valid_measured_dt_count': len(keep), 'raw_skipped_interval_count': len(measured_dt)-len(keep),
             'raw_skipped_intervals': [{'end_time_s': float(ft[i+1]-base), 'dt_s': float(d)}
                                       for i, d in enumerate(measured_dt) if not 0 < d <= .1],
             'imu_timestamp_token_identity': True, 'rpy_source_row_count': len(rp),
             'a1_row_count': len(a1_rows), 'a1_gnss18_shared_epoch_count': len(supported_a1),
             'a1_serialized_yaw_max_abs_difference_deg': max(yaw_deltas, default=0.),
             'a1_serialized_yaw_check_tolerance_deg': 1e-6,
             'pvt_row_count': len(pvt_keys), 'same_epoch_rv_identity': True,
             'gps_week': gps_week, 'leap_seconds': 18, 'scale_reapplied': False}
    return arrays, audit


def process_sources(code_root):
    paths = {Path(__file__).resolve(), code_root/'scripts/paper_rebuild/clean5_calibrate_sensors.py'}
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and Path(path).suffix == '.py' and code_root in Path(path).resolve().parents:
            paths.add(Path(path).resolve())
    return {str(p.relative_to(code_root)): sha256_file(p) for p in sorted(paths)}


def worker(registry, contract, contract_path, root, code_commit):
    spec = contract['calibration']
    paths = verify_input_pins(spec, registry)
    arrays, input_audit = load_arrays(paths, spec)
    summary, residuals, variances, windows = calibrate_arrays(**arrays)
    process = process_sources(registry.code_root)
    provenance = {**FLAGS, 'code_commit': code_commit, 'config_hash': sha256_file(contract_path),
                  'contract_sha256': sha256_file(contract_path),
                  'input_sha256': {k: {'path': spec['inputs'][k]['path'], 'sha256': spec['inputs'][k]['sha256']} for k in sorted(paths)},
                  'raw_source_hashes': {k: spec['inputs'][k]['sha256'] for k in ('go2_body', 'pvt_raw', 'status')},
                  'provider_hashes': {k: spec['inputs'][k]['sha256'] for k in ('provider_bundle', 'imu_increment', 'gnss_v2', 'a1')},
                  'process_source_sha256': process,
                  'process_sha256': hashlib.sha256(json.dumps(process, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
    parameters = [{'axis': name, 'solver_parameter_index': i, **summary['axes'][name]} for i, name in enumerate(AXES)]
    for filename, rows in [('LAG_RESIDUALS.csv', residuals), ('LAG_VARIANCE_FIT.csv', variances),
                            ('WINDOW_MEAN_ACCELERATION.csv', windows), ('CALIBRATED_PARAMETERS.csv', parameters)]:
        dump_csv(root/filename, rows)
    audit = {**provenance, 'input_audit': input_audit, 'summary': summary,
             'lag_variances': variances, 'window_means': windows, 'retry_count': 0}
    write_json(root/'CALIBRATION_AUDIT.json', audit)
    model = {**provenance, **summary, 'schema_version': 'paper_rebuild.clean5.calibrated_sensor_model.values.v1',
             'family': 'CLEAN5_CALIBRATED', 'classification': contract['classification'],
             's': spec['s'], 'calibration_dataset': 'BY2', 'calibration_count': 1,
             'blind_transfer_datasets': ['BY2H', 'BY2O'], 'refit_allowed': False,
             'q': [summary['axes'][a]['q_m2ps3'] for a in AXES],
             'c': [summary['axes'][a]['c_m2ps2'] for a in AXES],
             'window_counts': [summary['axes'][a]['nonempty_window_count'] for a in AXES],
             'lag_sample_counts': {r['lag_ms']: r['sample_count'] for r in variances if r['axis'] == AXES[0]},
             'lag_variances': variances, 'window_means': windows,
             'fallback_status': {a: summary['axes'][a]['status'] for a in AXES},
             'frozen_arw': spec['frozen_arw'], 'frozen_gbstd': spec['frozen_gbstd'],
             'frozen_initbastd': spec['frozen_initbastd'],
             'arw_policy': spec['arw_policy'], 'c_role': 'GNSS_VELOCITY_NOISE_DIAGNOSTIC_ONLY'}
    with (root/'CLEAN5_CALIBRATED_SENSOR_MODEL.yaml').open('x') as stream:
        yaml.safe_dump(model, stream, sort_keys=False, allow_unicode=True)
    verify_input_pins(spec, registry)
    write_json(root/'CALIBRATION_CHILD_TERMINAL.json', {**provenance, 'status': summary['status'],
               'fallback_axis_count': summary['fallback_axis_count'],
               'model_sha256': sha256_file(root/'CLEAN5_CALIBRATED_SENSOR_MODEL.yaml'),
               'tables': {name: sha256_file(root/name) for name in spec['output_tables']}})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    for name in ('code-root', 'paths-config'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--code-freeze-commit', required=True)
    parser.add_argument('--_child', action='store_true')
    args = parser.parse_args(argv)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    local = yaml.safe_load(args.paths_config.read_text())['paths']
    registry = SimpleNamespace(code_root=args.code_root.resolve(), raw_root=Path(local['raw_root']).resolve(),
                               clean_root=Path(local['clean_root']).resolve())
    state = execution_state(registry.code_root, args.code_freeze_commit)
    contract_path = registry.code_root/CONTRACT
    contract = yaml.safe_load(contract_path.read_text())
    spec = contract['calibration']
    if (spec['dataset_id'] != 'BY2' or spec['base_variant'] != 'V2s'
            or tuple(spec['fit']['lag_milliseconds']) != LAGS_MS
            or spec['window_seconds'] != [66., 340.]):
        raise ValueError('Calibration contract mathematical scope mismatch')
    root = resolve(contract['calibration_root'], registry)
    expected = registry.clean_root/'stages/CLEAN5_CALIBRATED_SENSOR_MODEL/00_CALIBRATION'
    if root != expected or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Unauthorized calibration output root')
    if args._child:
        return worker(registry, contract, contract_path, root, args.code_freeze_commit)
    root.mkdir(parents=True, exist_ok=False)
    write_json(root/'CALIBRATION_STARTED.json', {**FLAGS, 'code_commit': args.code_freeze_commit,
               'code_state': state, 'contract_sha256': sha256_file(contract_path), 'retry_count': 0})
    log = root/'CALIBRATION_OPENAT.strace'
    command = [shutil.which('strace') or 'strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat,execve',
               '-o', str(log), sys.executable, '-B', str(registry.code_root/'scripts/paper_rebuild/clean5_calibrate_sensors.py'),
               '--code-root', str(registry.code_root), '--paths-config', str(args.paths_config),
               '--code-freeze-commit', args.code_freeze_commit, '--_child']
    try:
        result = run_process_group(command, cwd=registry.code_root, timeout_seconds=1800,
                                    timeout_message='P06 calibration timeout', launch_failure_message='P06 calibration launch failed')
        (root/'stdout.log').write_text(result.stdout)
        (root/'stderr.log').write_text(result.stderr)
        records = audited_open_records(log, registry.code_root)
        audit = strict_open_audit(records, raw_root=registry.raw_root, clean_root=registry.clean_root,
                                  output_root=root, input_paths=[resolve(p['path'], registry) for p in spec['inputs'].values()])
        audit.update(exit_code=result.returncode, strace_sha256=sha256_file(log), command=command)
        audit['pass'] = audit['pass'] and result.returncode == 0
        write_json(root/'CALIBRATION_EXECUTION_AUDIT.json', audit)
        if not audit['pass']:
            raise RuntimeError('Calibration child/audit failed: '+result.stderr[-2000:])
        if execution_state(registry.code_root, args.code_freeze_commit) != state:
            raise ValueError('Detached calibration snapshot changed')
        terminal = json.loads((root/'CALIBRATION_CHILD_TERMINAL.json').read_text())
        terminal.update(execution_audit_sha256=sha256_file(root/'CALIBRATION_EXECUTION_AUDIT.json'),
                        strace_sha256=sha256_file(log), retry_count=0,
                        ready_for_model_freeze=terminal['status'] == 'CALIBRATION_COMPLETE')
        write_json(root/'CALIBRATION_TERMINAL.json', terminal)
        print('P06 A '+terminal['status']+'; solver=0 evaluator=0 forbidden opens=0', flush=True)
        return 0 if terminal['ready_for_model_freeze'] else 2
    except Exception as exc:
        write_json(root/'CALIBRATION_FAILURE.json', {**FLAGS, 'status': 'FAILED', 'error': str(exc),
                   'code_commit': args.code_freeze_commit, 'retry_count': 0})
        raise
