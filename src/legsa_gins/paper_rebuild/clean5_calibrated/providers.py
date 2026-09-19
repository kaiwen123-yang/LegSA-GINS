"""Frozen V2 observations with one BY2-calibrated scale and current-sample IMU."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import numpy as np
import yaml

from ...input_generation.imu_txt_builder import (
    build_process_data_imu_rows, parse_sportmodestate_text, euler_rpy_deg_to_matrix, _matvec,
)
from ..clean5_parity.runtime import resolve, write_json
from ..clean5_parity.input_audit import csv_rows
from ..manifest import sha256_file

INPUT_KEYS = ('imupath', 'gnsspath', 'raw_doppler_factor_path',
              'go2_attitude_prior_path', 'go2_horizontal_velocity_prior_path')
FILES = dict(zip(INPUT_KEYS, ('CALIBRATED_IMU.imu', 'CALIBRATED_GNSS.gnss', 'RAW_DOPPLER.csv',
                             'GO2_ATTITUDE_PRIOR.csv', 'GO2_HORIZONTAL_VELOCITY_PRIOR.csv')))
FLAGS = {'synthetic_data_used': False, 'semisynthetic_data_used': False, 'trace_used_online': False,
         'receiver_imu_as_body_imu': False, 'final_v23_output_solver_input': False,
         'LegSA_output_solver_input': False, 'per_case_tuning': False, 'output_only_correction': False,
         'epoch_deleted_for_metric': False, 'old_runtime_input_count': 0}


def forbidden_data_path(path):
    path = Path(path)
    return (any(s.lower() in ('.bag', '.fpl') for s in path.suffixes)
            or path.name.lower().startswith('trace_') or path.name.lower().startswith('trace.'))


def checked(pin, registry):
    path = resolve(pin['path'], registry)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unconfined/symlink pinned input')
    if forbidden_data_path(path) or sha256_file(path) != pin['sha256']:
        raise ValueError('Forbidden or changed pinned input: '+str(path))
    return path


def _token(value, precision):
    return format(float(format(float(value), '.12g')), '.'+str(precision)+'f')


def scale_current_sample_payload(*, baseline_rows, baseline_text, frames, scale):
    """Use unrounded installed FRD current force, preserving original gyro/time tokens."""
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Invalid frozen scale')
    fields = ('dtheta_x', 'dtheta_y', 'dtheta_z', 'dvel_x', 'dvel_y', 'dvel_z')
    reconstructed = ''.join(_token(r['time'], 6)+' '+' '.join(_token(r[k], 8) for k in fields)+'\n'
                            for r in baseline_rows)
    if reconstructed != baseline_text:
        raise ValueError('Frozen current-sample IMU byte reconstruction failed')
    indices = [i for i in range(1, len(frames)) if 0 < frames[i]['timestamp']-frames[i-1]['timestamp'] <= .1]
    tokens = [line.split() for line in baseline_text.splitlines()]
    if len(indices) != len(tokens) or len(indices) != len(baseline_rows):
        raise ValueError('Raw/frozen IMU interval mapping mismatch')
    rotation = euler_rpy_deg_to_matrix(-1, 0, 0)
    output = []
    for row, original, i in zip(baseline_rows, tokens, indices):
        dt = frames[i]['timestamp']-frames[i-1]['timestamp']
        if dt != row['dt']:
            raise ValueError('Frozen measured-dt identity mismatch')
        a = frames[i]['accelerometer']
        force = np.asarray(_matvec(rotation, [a[0], -a[1], -a[2]]), float)
        dvel = (force*scale)*dt
        output.append(' '.join(original[:4]+[_token(v, 8) for v in dvel])+'\n')
    text = ''.join(output)
    if any(a.split()[:4] != b.split()[:4] for a, b in zip(text.splitlines(), baseline_text.splitlines())):
        raise ValueError('Scale changed time/gyro tokens')
    return text, {'frozen_unscaled_imu_byte_identity': True, 'timestamp_and_gyro_tokens_unchanged': True,
                  'row_count': len(output), 'raw_frame_count': len(frames),
                  'skipped_interval_count': len(frames)-1-len(indices),
                  's': scale, 'scale_fitted_here': False, 'external_preprocessing_called': False,
                  'integration_convention': 'frozen current sample, measured dt, FLU->FRD, Rx(-1 degree)',
                  'first_1000_gyro_bias': 'unchanged frozen builder input-side calibration',
                  'accel_scale_applied_before_dt': True, 'previous_sample_ZOH_used': False}


def verify_model(contract, registry):
    path = checked(contract['model'], registry)
    model = yaml.safe_load(path.read_text())
    admission_path = checked(contract['admission'], registry)
    admission = json.loads(admission_path.read_text())
    if (admission['status'] != 'PASS_CORRECTED_AUDIT_NO_RECOMPUTATION'
            or admission.get('ready_for_model_freeze') is not True
            or admission['model_sha256'] != contract['model']['sha256']
            or model['status'] != 'CALIBRATION_COMPLETE' or model['calibration_count'] != 1
            or model['calibration_dataset'] != 'BY2' or model['refit_allowed'] is not False):
        raise ValueError('Frozen model/admission identity failed')
    for key in ('vrw', 'abstd'):
        if len(model[key]) != 3 or not all(math.isfinite(v) and v >= 0 for v in model[key]):
            raise ValueError('Invalid calibrated noise vector '+key)
    if not math.isfinite(model['s']) or model['s'] <= 0:
        raise ValueError('Invalid calibrated scale')
    return model


def checkpoint_inputs(*, registry, contract, dataset):
    spec = contract['sequences'][dataset]
    if set(spec['raw_inputs']) != {'body', 'status', 'gnss1', 'gnss2'}:
        raise ValueError('Only four declared observation raw roles are permitted')
    lock_path = checked(spec['raw_lock'], registry)
    locked = {r['relative_path']: r['sha256'] for r in csv_rows(lock_path)}
    sources = {}
    for role, pin in spec['raw_inputs'].items():
        path = checked(pin, registry)
        relative = path.relative_to(registry.raw_root).as_posix()
        if locked.get(relative) != pin['sha256']:
            raise ValueError('Raw input not bound to immutable lock: '+role)
        sources[role] = {'path': str(path), 'sha256': pin['sha256'], 'raw_relative_path': relative}
    return {'status': 'PASS', 'dataset_id': dataset, 'raw_role_count': len(sources),
            'verified_count': len(sources), 'raw_source_hashes': sources,
            'raw_lock_sha256': spec['raw_lock']['sha256'], 'trace_bag_fpl_hashed': False, **FLAGS}


def source_inputs(*, registry, contract, dataset):
    spec = contract['sequences'][dataset]
    bundle = json.loads(checked(spec['source_bundle'], registry).read_text())
    inputs = bundle['variants'][spec['source_variant']]['providers']
    if set(inputs) != set(INPUT_KEYS):
        raise ValueError('Frozen V2 provider roles mismatch')
    for pin in inputs.values():
        checked(pin, registry)
    if inputs['imupath']['sha256'] != spec['original_imu']['sha256']:
        raise ValueError('Frozen V2 original IMU identity differs')
    if bundle['baseline_median_m'] != spec['baseline_median_m']:
        raise ValueError('Frozen baseline identity differs')
    return bundle, inputs


def generate_provider(*, registry, contract, stage_root, dataset, code_commit):
    spec = contract['sequences'][dataset]
    model = verify_model(contract, registry)
    raw = checkpoint_inputs(registry=registry, contract=contract, dataset=dataset)
    source, inputs = source_inputs(registry=registry, contract=contract, dataset=dataset)
    output = Path(stage_root)/'02_CALIBRATED_PROVIDERS'/dataset
    output.mkdir(parents=True, exist_ok=False)
    if dataset == 'BY2':
        if spec['source_variant'] != 'V2s' or source['audit']['s'] != model['s']:
            raise ValueError('BY2 source must be the calibrated original V2s')
        payload = checked(inputs['imupath'], registry).read_text()
        imu_audit = {'BY2_V2s_copied_byte_exact': True, 'row_count': len(payload.splitlines()),
                     's': model['s'], 'scale_fitted_here': False, 'previous_sample_ZOH_used': False,
                     'timestamp_and_gyro_tokens_unchanged': True}
    else:
        original_imu = checked(spec['original_imu'], registry)
        body = checked(spec['raw_inputs']['body'], registry)
        baseline_rows, builder_audit = build_process_data_imu_rows(body, base_time=spec['base_time'])
        frames = parse_sportmodestate_text(body)
        payload, imu_audit = scale_current_sample_payload(baseline_rows=baseline_rows,
            baseline_text=original_imu.read_text(), frames=frames, scale=model['s'])
        imu_audit['frozen_builder_audit'] = builder_audit
    providers = {}
    copies = []
    for key in INPUT_KEYS:
        path = output/FILES[key]
        original = checked(inputs[key], registry)
        with path.open('xb') as stream:
            stream.write(payload.encode() if key == 'imupath' else original.read_bytes())
        providers[key] = {'path': str(path), 'sha256': sha256_file(path),
                          **{k: v for k, v in inputs[key].items() if k not in ('path', 'sha256')}}
        same = providers[key]['sha256'] == inputs[key]['sha256']
        if key != 'imupath' or dataset == 'BY2':
            if not same:
                raise ValueError('Required provider byte-copy identity failed: '+key)
        copies.append({'key': key, 'source_path': str(original), 'source_sha256': inputs[key]['sha256'],
                       'output_sha256': providers[key]['sha256'], 'byte_equal': same})
    gnss = np.loadtxt(providers['gnsspath']['path'], ndmin=2)
    if gnss.shape[1] != 18 or not np.isfinite(gnss).all() or not np.isin(gnss[:, 15:], (0, 1)).all():
        raise ValueError('Frozen V2 GNSS18 validity contract failed')
    family = 'CLEAN5_CALIBRATED_'+dataset
    bundle = {**FLAGS, 'dataset_id': dataset, 'data_mode': registry.sequences[dataset].data_mode,
              'provider_family': family, 'code_commit': code_commit,
              'config_hash': hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest(),
              'model_sha256': contract['model']['sha256'], 'model_freeze_commit': contract['model_freeze_commit'],
              'calibration_dataset': 'BY2', 'blind_transfer': dataset != 'BY2', 's': model['s'],
              'baseline_median_m': spec['baseline_median_m'], 'raw_source_hashes': raw['raw_source_hashes'],
              'source_provider_bundle': spec['source_bundle'],
              'variants': {'V2s': {'variant_id': 'V2s', 'provider_family': family, 'providers': providers}},
              'audit': {'imu': imu_audit, 'provider_copy_ledger': copies,
                        'gnss_row_count': len(gnss), 'gnss_columns': 18,
                        'yaw_valid_count': int(gnss[:, 17].sum()), 'rv_valid_count': int(gnss[:, 16].sum()),
                        'parameter_source': 'one frozen BY2 model; no per-sequence scale/noise fitting',
                        'base_time': spec['base_time'], 'window_seconds': spec['window_seconds']}}
    for name in ('PROVIDER_MANIFEST.json', 'CALIBRATED_PROVIDER_BUNDLE.json'):
        write_json(output/name, bundle)
    return bundle


def verify_bundle(bundle):
    if set(bundle['variants']) != {'V2s'} or not bundle['provider_family'].startswith('CLEAN5_CALIBRATED_'):
        raise ValueError('Calibrated provider family/variant mismatch')
    inputs = bundle['variants']['V2s']['providers']
    if set(inputs) != set(INPUT_KEYS):
        raise ValueError('Calibrated provider role mismatch')
    for pin in inputs.values():
        path = Path(pin['path'])
        if forbidden_data_path(path) or any(p.is_symlink() for p in (path, *path.parents)) or sha256_file(path) != pin['sha256']:
            raise ValueError('Calibrated provider mutated')
