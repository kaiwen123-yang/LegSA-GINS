"""P-13 observation providers and their preregistered residual identity gates.

No native solver, evaluator, trace, capture, or historical performance reader is
used here. The existing injection functions remain the scientific authority.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib
import io
import json
from pathlib import Path
import re
import sys

import numpy as np
import yaml

from ..canonical541 import provider_generator as canonical
from ..clean5_degradation import providers as old
from ..clean5_degradation.common import FLAGS, pinned, resolve, resolved_pins, write_json
from ..manifest import sha256_file

STAGE_NAME = 'CLEAN6_SENSOR_MODEL_V21'
K_HV = 1.0 / 0.962142
SIGMA_HV = 0.132838
SIGMA_YAW = 2.933193
TOLERANCE = 1e-6
_CACHE = {}


class ReproductionGateFailure(ValueError):
    """A P-13 scientific stop, distinct from bookkeeping errors."""


def _audits(reg):
    scripts = str(reg.code_root / 'scripts/paper_rebuild')
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return tuple(importlib.import_module(name) for name in (
        'clean6_hv_prior_residual_stats', 'clean6_hv_frame_audit',
        'clean6_hv_a1_yaw_diagnostic', 'clean6_sensor_model_closeout_audit'))


def _identity(contract, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Full frozen provider code commit required')
    if not contract.get('executable') or not contract.get('preregistered'):
        raise ValueError('Executable preregistered P-13 contract required')
    group = contract['sensor_model_group']
    digest = hashlib.sha256(json.dumps(group, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=False).encode()).hexdigest()
    if digest != contract['sensor_model_group_hash']:
        raise ValueError('SENSOR_MODEL_V21 group hash mismatch')
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':'),
                                   ensure_ascii=False).encode()).hexdigest()


def _contract_hash(contract, reg, commit):
    _identity(contract, commit)
    path = reg.code_root/'configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml'
    if yaml.safe_load(path.read_text()) != contract:
        raise ValueError('Provider contract differs from frozen tracked contract')
    return sha256_file(path)


def _frozen_contract_pin(spec, reg):
    path = resolve(spec['path'], reg)
    if not path.is_absolute():
        path = reg.code_root/path
    return old._checked_pin({'path': str(path), 'sha256': spec['sha256']})


def _verify_injection_identity(v21, v2, reg, case, mapping):
    key = ('injection_registration', v21['sensor_model_group_hash'])
    if key not in _CACHE:
        core = _frozen_contract_pin(v21['frozen_identities']['core_contract'], reg)
        if yaml.safe_load(core.read_text()) != v2:
            raise ValueError('V2 contract changed before injection')
        for pin in v2['sources']['frozen_injection_library']:
            pinned(pin, reg)
        with pinned(v2['sources']['case_registry'], reg).open(newline='') as stream:
            cases = {r['case_id']: r for r in csv.DictReader(stream)}
        addendum = yaml.safe_load(_frozen_contract_pin(v21['frozen_identities']['addendum_contract'], reg).read_text())
        cases.update({r['case_id']: r for r in addendum['case_rows']})
        _CACHE[key] = cases
    expected = _CACHE[key].get(case['case_id'])
    if expected is None or any(str(case.get(k)) != str(v) for k, v in expected.items()):
        raise ValueError('Case differs from frozen case registration')
    if case['degradation_type_id'] not in ('D61', 'D62'):
        registered = next(m for m in v2['providers']['mapping'] if m['case_id'] == case['case_id'])
        if any(mapping.get(k) != v for k, v in registered.items()):
            raise ValueError('Injection mapping differs from frozen registration')


def _root(path):
    root = Path(path)
    if not root.is_absolute() or '..' in root.parts or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Absolute non-symlink attempt-owned output required')
    return root


def _resume(root, config_hash, commit):
    seal_path = root / 'PROVIDER_SEAL.json'
    if not root.exists():
        return None
    if not seal_path.is_file():
        raise ValueError('Unsealed provider output exists; preserve it, no overwrite')
    seal = json.loads(seal_path.read_text())
    if seal['config_hash'] != config_hash or seal['code_commit'] != commit:
        raise ValueError('Sealed provider identity differs')
    for relative, digest in seal['files_sha256'].items():
        path = root / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or path.is_symlink() or sha256_file(path) != digest:
            raise ValueError('Provider seal mismatch')
    bundle = json.loads((root / 'PROVIDER_BUNDLE.json').read_text())
    for pin in bundle['providers'].values():
        old._checked_pin(pin)
    return bundle


def _seal(root, result):
    write_json(root / 'PROVIDER_BUNDLE.json', result)
    files = {p.relative_to(root).as_posix(): sha256_file(p) for p in sorted(root.iterdir()) if p.is_file()}
    write_json(root / 'PROVIDER_SEAL.json', {'status': 'SEALED', 'config_hash': result['config_hash'],
               'code_commit': result['code_commit'], 'files_sha256': files})


def _write(path, payload):
    with Path(path).open('xb') as stream:
        stream.write(payload)
    return {'path': str(path), 'sha256': sha256_file(path), 'storage_mode': 'materialized'}


def _csv_table(path):
    fields, rows = old._csv(Path(path))
    return canonical.ProviderTable(fields, rows)


def interpolate_a1(times, a1_times, a1_yaw_deg, *, maximum_gap_s=1.2):
    """Unwrapped linear interpolation, closed observations and open long gaps."""
    times, at, yaw = np.asarray(times, float), np.asarray(a1_times, float), np.asarray(a1_yaw_deg, float)
    if len(at) != len(yaw) or not np.isfinite(at).all() or not np.isfinite(yaw).all() or np.any(np.diff(at) <= 0):
        raise ValueError('A1 must be finite, ordered, unique observation epochs')
    if not len(at):
        return None, np.zeros(len(times), bool)
    values = np.interp(times, at, np.unwrap(np.deg2rad(yaw)))
    support = (times >= at[0]) & (times <= at[-1])
    if len(at) > 1:
        index = np.clip(np.searchsorted(at, times, side='right') - 1, 0, len(at)-2)
        support &= ~((np.diff(at)[index] > maximum_gap_s) & (times > at[index]) & (times < at[index+1]))
    return values, support


def rotate_flu_to_ned(velocity, roll, pitch, yaw):
    v = np.asarray(velocity, float) * [1., -1., -1.]
    cr, sr, cp, sp = np.cos(roll), np.sin(roll), np.cos(-np.asarray(pitch)), np.sin(-np.asarray(pitch))
    cy, sy = np.cos(yaw), np.sin(yaw)
    return np.column_stack((
        cy*cp*v[:, 0] + (cy*sp*sr-sy*cr)*v[:, 1] + (cy*sp*cr+sy*sr)*v[:, 2],
        sy*cp*v[:, 0] + (sy*sp*sr+cy*cr)*v[:, 1] + (sy*sp*cr-cy*sr)*v[:, 2]))


def correct_hv(table, body, yaw_rows, *, timing_fault=False):
    """Preserve row identities/payloads; invalid measurements never update."""
    result = copy.deepcopy(table)
    extra = ('valid', 'go2_source_valid', 'a1_heading_valid')
    result.fields = tuple(dict.fromkeys((*result.fields, *extra)))
    indices = np.array([int(r[canonical.D57_ORIGINAL_ROW_ID]) if timing_fault else i
                        for i, r in enumerate(result.rows)])
    if len(indices) != len(body) or set(indices) != set(range(len(body))):
        raise ValueError('HV original row identity mismatch')
    a1 = [r for r in yaw_rows if old._valid(r)]
    at = np.array([float(r['time']) for r in a1])
    if not timing_fault:
        at = np.rint(at*1000)/1000.
    times = np.array([float(r['time']) for r in result.rows])
    yaw, support = interpolate_a1(times, at, [float(r['yaw_deg']) for r in a1])
    transformed = None if yaw is None else K_HV * rotate_flu_to_ned(
        body[indices, 3:6], body[indices, 1], body[indices, 2], yaw)
    for i, row in enumerate(result.rows):
        source_valid = str(row.get('go2_source_valid', old._valid(row))).lower() in {'true', '1'}
        if transformed is not None:
            row['vn'], row['ve'] = (repr(float(x)) for x in transformed[i])
        row.update(std_vn=str(SIGMA_HV), std_ve=str(SIGMA_HV),
                   valid=str(int(source_valid and support[i])),
                   update_flag=str(bool(source_valid and support[i])),
                   go2_source_valid=str(source_valid), a1_heading_valid=str(bool(support[i])),
                   frame_candidate='FLU_to_FRD_Go2_RP_injected_A1_NED',
                   prior_policy='SENSOR_MODEL_V21_horizontal_weak_prior')
        if not support[i]:
            row['reason_codes'] = 'a1_heading_unavailable_no_update'
    return result


def correct_rp(table, raw):
    result = copy.deepcopy(table)
    times = np.array([float(r['time']) for r in result.rows])
    indices = np.searchsorted(raw[:, 0], times)
    right = np.minimum(indices, len(raw)-1)
    left = np.maximum(right-1, 0)
    indices = np.where(abs(raw[left, 0]-times) <= abs(raw[right, 0]-times), left, right)
    if np.max(abs(raw[indices, 0]-times)) >= 1e-9:
        raise ValueError('RP raw row identity mismatch')
    for row, source in zip(result.rows, raw[indices]):
        if abs(float(row['roll_rad'])-source[1]) > 1e-12 or abs(float(row['pitch_rad'])-source[2]) > 1e-12:
            raise ValueError('RP source frame tokens differ from pinned raw')
        row['pitch_rad'] = repr(float(-source[2]))
        if any(abs(float(row[k])-np.deg2rad(1.6)) > 1e-12 for k in ('std_roll_rad', 'std_pitch_rad')):
            raise ValueError('RP frozen std differs from 1.6 degrees')
    return result


def gnss_tokens(path):
    return [line.split() for line in Path(path).read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]


def yaw_std_tokens(rows):
    out = copy.deepcopy(rows)
    for row in out:
        if len(row) not in (15, 18):
            raise ValueError('Only registered GNSS15/18 formats allowed')
        row[14] = str(SIGMA_YAW)
    return out


def compare_gnss_tokens(before, after, *, nominal=False):
    if len(before) != len(after):
        raise ValueError('GNSS row identity mismatch')
    for left, right in zip(before, after):
        if len(left) != len(right) or left[:14]+left[15:] != right[:14]+right[15:]:
            raise ValueError('GNSS non-yaw-std token changed')
        if nominal and right[14] != str(SIGMA_YAW):
            raise ValueError('Nominal yaw std token differs')
    return {'status': 'PASS', 'rows': len(after), 'columns': len(after[0]),
            'all_non_yaw_std_tokens_equal': True, 'nominal_yaw_std_all_2_933193': nominal}


def _compare(expected, actual, path='', differences=None):
    differences = [] if differences is None else differences
    if isinstance(expected, dict):
        for key, value in expected.items():
            if key not in actual:
                raise ReproductionGateFailure('Missing statistic '+path+'/'+key)
            _compare(value, actual[key], path+'/'+key, differences)
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ReproductionGateFailure('Statistic length mismatch '+path)
        for i, (left, right) in enumerate(zip(expected, actual)):
            _compare(left, right, path+'/'+str(i), differences)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        delta = abs(float(actual)-float(expected))
        if not np.isfinite(delta) or delta > TOLERANCE:
            raise ReproductionGateFailure('Residual reproduction failed '+path+': '+str(delta))
        differences.append({'statistic': path, 'expected': expected, 'actual': actual, 'absolute_difference': delta})
    elif expected != actual:
        raise ReproductionGateFailure('Statistic identity mismatch '+path)
    return differences


def hv_statistics(data, velocity, modules):
    statsmod, frame, _, _ = modules
    residual = velocity-data['pvt']
    c, s = np.cos(data['yaw']), np.sin(data['yaw'])
    values = np.column_stack((residual, c*residual[:, 0]+s*residual[:, 1], -s*residual[:, 0]+c*residual[:, 1]))
    speed = np.linalg.norm(data['pvt'], axis=1)
    acf = frame.slot_acf(data['t'], values, data['blocks'])
    return {'n': len(values), 'axes_mps': {a: statsmod.stats(values[:, i]) for i, a in enumerate(frame.AXES)},
            'sigma_HV_mps': float(np.sqrt(np.mean(np.var(residual, axis=0, ddof=1)))),
            'mean_NE_norm_mps': float(np.linalg.norm(residual.mean(axis=0))),
            'mean_along_right_norm_mps': float(np.linalg.norm(values[:, 2:].mean(axis=0))),
            'bins': {k: {a: statsmod.stats(values[m, i]) for i, a in enumerate(frame.AXES)} for k, m in frame.speed_bins(speed).items()},
            'horizontal_speed_OLS_vs_PVT': frame.regression(speed, np.linalg.norm(velocity, axis=1)),
            'acf_at_1_s': dict(zip(frame.AXES, acf['at_1_s']['rho'])),
            'acf_first_nonpositive': dict(zip(frame.AXES, acf['first_nonpositive'])),
            'acf_1s_pair_count': acf['at_1_s']['pair_count']}


def validate_residuals(data, providers, frame_reference, rp_reference, modules):
    """Re-read generated values; compare every H-A and static/slow RP statistic."""
    statsmod, frame, _, p12 = modules
    hv = _csv_table(providers['go2_horizontal_velocity_prior_path']['path'])
    values = np.array([[float(r['vn']), float(r['ve'])] for r in hv.rows])[data['keep']]
    if not all(old._valid(r) for r, keep in zip(hv.rows, data['keep']) if keep):
        raise ReproductionGateFailure('P11b matched sample was invalidated')
    unscaled = hv_statistics(data, values/K_HV, modules)
    differences = _compare(frame_reference['hypotheses']['H-A'], unscaled, 'HV_inverse_scaled')
    scaled = hv_statistics(data, values, modules)
    rp = _csv_table(providers['go2_attitude_prior_path']['path'])
    rp_times = np.array([float(r['time']) for r in rp.rows])
    rp_vals = np.array([[float(r['roll_rad']), float(r['pitch_rad'])] for r in rp.rows])
    im, _ = p12.imu_fields(data['body_bytes'])
    im[:, 0] -= data['spec']['base_time']
    mask = np.isfinite(im[:, :7]).all(axis=1)
    t, acc = im[mask, 0], im[mask, 4:7]*[1, -1, -1]
    indices = statsmod.nearest(rp_times, t)
    if np.max(abs(rp_times[indices]-t)) >= 1e-9:
        raise ReproductionGateFailure('RP P12 raw row matching failed')
    corrected = rp_vals[indices]
    gravity = p12.gravity_angles(acc)
    residual = np.rad2deg(frame.wrap(corrected-gravity))
    static = []
    for window in rp_reference['static_windows']:
        if window['interval_s'] is None:
            static.append(window)
            continue
        lo, hi = window['interval_s']
        selected = (t >= lo) & (t <= hi)
        result = {a: statsmod.stats(residual[selected, i]) for i, a in enumerate(('roll', 'pitch'))}
        differences.extend(_compare(window['RP_converted_minus_gravity_deg'], result, 'RP_static/'+window['name']))
        static.append({'name': window['name'], 'interval_s': window['interval_s'], 'n': int(selected.sum()), 'residual_deg': result})
    idx = statsmod.nearest(data['pt'], t)
    lo, hi = data['spec']['window_seconds']
    slow = (t >= lo)&(t <= hi)&(abs(t-data['pt'][idx]) <= .03)&(np.linalg.norm(data['pvt_full'][idx, :2], axis=1) < .8)
    slowstats = {a: statsmod.stats(residual[slow, i]) for i, a in enumerate(('roll', 'pitch'))}
    differences.extend(_compare(rp_reference['mounting_and_RP']['slow_RP']['residual_deg']['converted'], slowstats, 'RP_slow'))
    return {'status': 'PASS_HV_RP_REPRODUCTION', 'passed': True, 'absolute_tolerance': TOLERANCE,
            'maximum_absolute_difference': max(x['absolute_difference'] for x in differences),
            'compared_numeric_statistics': len(differences), 'statistic_differences': differences,
            'HV_inverse_scaled': unscaled, 'HV_final_scaled': scaled, 'RP_static': static, 'RP_slow': slowstats,
            'source': 'new provider files re-read; exact frozen raw/PVT/A1 matching masks', 'trace_opened': False}


def generate_bases(v21_contract, v2_contract, reg, output, code_commit):
    """Create output/{BY2,BY2H,BY2O}; return dataset bundles plus gate manifest."""
    config_hash = _contract_hash(v21_contract, reg, code_commit)
    root = _root(output)
    modules = _audits(reg)
    statsmod, frame, diagnostic, _ = modules
    inputs = statsmod.Inputs({k: str(getattr(reg, k)) for k in ('code_root', 'clean_root', 'raw_root')})
    reference = {k: json.loads(inputs.pin(v21_contract['frozen_identities'][k])) for k in ('p11b', 'p12')}
    prior_path = frame.ROOT+'HV_PRIOR_RESIDUAL_STATS.json'
    prior = json.loads(inputs.read(prior_path, frame.P11A_SHA))
    cp = '<CODE_ROOT>/configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml'
    audit_contract = yaml.safe_load(inputs.read(cp, prior['input_files'][cp]['sha256']))
    root.mkdir(parents=True, exist_ok=True)
    bundles = {}
    for dataset in v21_contract['scope_and_accounting']['sequences']:
        destination = root/dataset
        resumed = _resume(destination, config_hash, code_commit)
        if resumed is not None:
            bundles[dataset] = resumed
            continue
        spec = v2_contract['sequences'][dataset]
        pins = resolved_pins(spec['providers'], reg)
        for pin in pins.values():
            old._checked_pin(pin)
        data = diagnostic.load_observations(inputs, prior, audit_contract, dataset)
        if spec['raw_inputs']['body']['sha256'] != data['cal']['raw_source_hashes']['body']['sha256']:
            raise ValueError('V2s raw body identity changed')
        # Preserve the complete frozen source schedule, including out-of-window rows.
        body = data['raw_complete'][:, [0, 1, 2, 7, 8, 9]]
        yawrows = [{'time': repr(float(r[0])), 'yaw_deg': repr(float(r[13])), 'valid': '1'}
                   for r in data['gnss'] if r[17] == 1]
        hv = correct_hv(_csv_table(pins['go2_horizontal_velocity_prior_path']['path']), body, yawrows)
        rp = correct_rp(_csv_table(pins['go2_attitude_prior_path']['path']), data['raw'])
        oldtokens = gnss_tokens(pins['gnsspath']['path'])
        tokens = yaw_std_tokens(oldtokens)
        gnss_gate = compare_gnss_tokens(oldtokens, tokens, nominal=True)
        destination.mkdir(exist_ok=False)
        providers = {role: {**pin, 'storage_mode': 'pinned_unchanged_pointer'} for role, pin in pins.items()}
        providers['gnsspath'] = _write(destination/'GNSS18.gnss', ''.join(' '.join(r)+'\n' for r in tokens).encode())
        providers['go2_attitude_prior_path'] = _write(destination/'GO2_ATTITUDE_PRIOR.csv', rp.canonical_bytes())
        providers['go2_horizontal_velocity_prior_path'] = _write(destination/'GO2_HORIZONTAL_VELOCITY_PRIOR.csv', hv.canonical_bytes())
        projection = _write(destination/'GNSS15.gnss', ''.join(' '.join(r[:15])+'\n' for r in tokens).encode())
        projection.update(solver_input=False, purpose='15-column token projection; formal runtime uses GNSS18 validity')
        with (destination/'GO2_BODY_SOURCE_SUPPORT.npz').open('xb') as stream:
            np.savez_compressed(stream, body=body)
        support = {'path': str(destination/'GO2_BODY_SOURCE_SUPPORT.npz'), 'sha256': sha256_file(destination/'GO2_BODY_SOURCE_SUPPORT.npz'), 'raw_body_sha256': spec['raw_inputs']['body']['sha256']}
        gate = validate_residuals(data, providers, reference['p11b']['sequences'][dataset], reference['p12']['sequences'][dataset], modules)
        gate['GNSS18'] = gnss_gate
        gate['GNSS15'] = compare_gnss_tokens([r[:15] for r in oldtokens], gnss_tokens(projection['path']), nominal=True)
        gate['unchanged_IMU_RD'] = {role: {'sha256': sha256_file(Path(providers[role]['path'])), 'passed': providers[role]['sha256'] == pins[role]['sha256']}
                                  for role in ('imupath', 'raw_doppler_factor_path')}
        for role, entry in gate['unchanged_IMU_RD'].items():
            entry['passed'] = entry['sha256'] == pins[role]['sha256']
            if not entry['passed']:
                raise ValueError('Frozen IMU/RD source changed: '+role)
        write_json(destination/'PROVIDER_VALIDATION.json', gate)
        result = {**FLAGS, 'schema_version': 'clean6.sensor_model_v21.base.v1', 'protocol_id': 'SENSOR_MODEL_V2_1',
                  'dataset_id': dataset, 'data_mode': 'real', 'providers': providers, 'GNSS15_projection': projection,
                  'body_support': support, 'raw_source_hashes': resolved_pins(spec['raw_inputs'], reg),
                  'raw_input_hashes': {k: v['sha256'] for k, v in spec['raw_inputs'].items()},
                  'provider_hashes': {k: v['sha256'] for k, v in providers.items()},
                  'base_provider_pins': pins, 'sensor_model_group_hash': v21_contract['sensor_model_group_hash'],
                  'code_commit': code_commit, 'config_hash': config_hash, 'case_root': str(destination),
                  'validation': gate, 'solver_execution_count': 0, 'evaluator_execution_count': 0,
                  'runtime_contract': {'gnss_columns': 18, 'gnss_row_count': len(tokens),
                      'position_valid_count': sum(int(r[15]) for r in tokens),
                      'rv_valid_count': sum(int(r[16]) for r in tokens),
                      'a1_valid_count': sum(int(r[17]) for r in tokens)}, 'input_files': dict(inputs.ledger)}
        _seal(destination, result)
        bundles[dataset] = result
        del data
    gate = {'status': 'PASS_THREE_SEQUENCE_PROVIDER_GATES', 'datasets': list(bundles),
            'maximum_absolute_difference': max(v['validation']['maximum_absolute_difference'] for v in bundles.values()),
            'sensor_model_group_hash': v21_contract['sensor_model_group_hash'], 'code_commit': code_commit,
            'config_hash': config_hash, 'trace_used_online': False}
    gatepath = root/'BASE_PROVIDER_GATES.json'
    if not gatepath.exists():
        write_json(gatepath, gate)
    elif json.loads(gatepath.read_text()) != gate:
        raise ValueError('Existing base gate identity differs')
    return {'bundles': bundles, 'gate': gate}


def _case_bases(v2, reg, base_bundle):
    key = (base_bundle['config_hash'], base_bundle['providers']['gnsspath']['sha256'])
    if key not in _CACHE:
        aux = resolved_pins(v2['providers']['auxiliary_roles'], reg)
        kw = {'auxiliary_roles': aux, 'base_time_s': v2['evaluation']['base_time'],
              'raw_input_hashes': base_bundle['raw_input_hashes']}
        corrected = old.build_base(base_bundle['providers'], **kw)
        original = old.build_base(resolved_pins(v2['providers']['roles'], reg), **kw)
        pin = base_bundle['body_support']
        old._checked_pin(pin)
        with np.load(pin['path'], allow_pickle=False) as data:
            body = data['body']
        _CACHE[key] = corrected, original, body
    return _CACHE[key]


def _inject(base, case, mapping):
    tid = case['degradation_type_id']
    if tid in ('D61', 'D62'):
        sources = ('gnss_position', 'receiver_velocity', 'raw_doppler') + (('dual_yaw',) if tid == 'D61' else ())
        bundle = base.bundle.clone()
        components = canonical._outage(bundle, case, sources, float(case['duration_s']))
        return bundle, components, {'degradation_type_id': tid, 'trace_read_count': 0, 'no_active_path': False}
    if tid in ('D22', 'D39'):
        return old._apply_count_intervals(base.bundle, case, mapping)
    return canonical.apply_degradation(base.bundle, case)


def generate_case(v21_contract, v2_contract, reg, base_bundle, case, mapping, output, code_commit):
    """Create output/case_id, compatible with the frozen five-role runtime API."""
    config_hash = _contract_hash(v21_contract, reg, code_commit)
    if base_bundle['dataset_id'] != 'BY2':
        raise ValueError('Frozen injected matrix requires BY2 base')
    _verify_injection_identity(v21_contract, v2_contract, reg, case, mapping or {})
    case_id, tid = case['case_id'], case['degradation_type_id']
    if '/' in case_id or '..' in case_id:
        raise ValueError('Unsafe case identity')
    root = _root(output)/case_id
    resumed = _resume(root, config_hash, code_commit)
    if resumed is not None:
        return resumed
    base, original, body = _case_bases(v2_contract, reg, base_bundle)
    mapping = resolved_pins(mapping or {}, reg)
    generated, components, semantics = _inject(base, case, mapping)
    reference, _, _ = _inject(original, case, mapping)
    # Direct HV faults already acted on the corrected base. Every yaw/time fault
    # must instead rebuild the dependency using the post-injection observations.
    if tid not in ('D53', 'D54'):
        generated.tables['go2_hv'] = correct_hv(generated.tables['go2_hv'], body, generated.tables['dual_yaw'].rows,
                                               timing_fault=tid == 'D57')
    rows, oldrows = old._gnss_rows(base, generated, tid), old._gnss_rows(original, reference, tid)
    token_gate = compare_gnss_tokens(oldrows, rows)
    if any(len(r) != 18 or any(float(v) not in (0, 1) for v in r[15:]) for r in rows):
        raise ValueError('GNSS18 validity gate failed')
    if any(float(a[0]) >= float(b[0]) for a, b in zip(rows, rows[1:])):
        raise ValueError('GNSS18 schedule not strictly increasing')
    a1_valid = sum(old._valid(r) for r in generated.tables['dual_yaw'].rows)
    hv_valid = sum(old._valid(r) for r in generated.tables['go2_hv'].rows)
    if a1_valid == 0 and hv_valid != 0:
        raise ValueError('A1 fully absent but HV remained valid')
    unchanged = {}
    for source in ('gnss_position', 'receiver_velocity', 'raw_doppler', 'source_quality_metadata'):
        equal = generated.tables[source].canonical_bytes() == reference.tables[source].canonical_bytes()
        if not equal:
            raise ValueError('Unaffected injection source changed: '+source)
        unchanged[source] = True
    root.mkdir(parents=True, exist_ok=False)
    if tid == 'D57':
        identity = {source: [{'original_row_id': int(row[canonical.D57_ORIGINAL_ROW_ID]),
                             'original_time': base.bundle.tables[source].rows[int(row[canonical.D57_ORIGINAL_ROW_ID])]['time'],
                             'generated_time': row['time']} for row in generated.tables[source].rows]
                    for source in canonical.D57_TIMING_SOURCE_IDS}
        write_json(root/'D57_SOURCE_ROW_IDENTITY.json', identity)
    providers = {r: {**pin, 'storage_mode': 'pinned_unchanged_pointer'} for r, pin in base.providers.items()}
    if rows != base.gnss_tokens:
        providers['gnsspath'] = _write(root/'GNSS18.gnss', ''.join(' '.join(r)+'\n' for r in rows).encode())
    for source, role in old.SOURCE_TO_ROLE.items():
        table = generated.tables[source]
        if table.canonical_bytes() != base.bundle.tables[source].canonical_bytes():
            providers[role] = _write(root/old.FILENAMES[role], table.canonical_bytes())
    audit_payloads = {}
    for source in ('dual_yaw', 'source_quality_metadata'):
        if generated.tables[source].canonical_bytes() != base.bundle.tables[source].canonical_bytes():
            audit_payloads[source] = _write(root/(source+'_AUDIT.csv'), generated.tables[source].canonical_bytes())
            audit_payloads[source]['solver_input'] = False
    projection = _write(root/'GNSS15.gnss', ''.join(' '.join(r[:15])+'\n' for r in rows).encode())
    projection['solver_input'] = False
    evidence = {'status': 'PASS_SENSOR_V21_INJECTION', 'passed': True, 'GNSS_tokens': token_gate,
                'unchanged_injection_sources': unchanged, 'a1_valid_count': a1_valid, 'hv_valid_count': hv_valid,
                'yaw_before_HV': True, 'D57_original_row_identity_retained': tid == 'D57',
                'canonical_injection_source_sha256': sha256_file(Path(canonical.__file__)),
                'trace_opened': False, 'no_invalid_source_enabled': True}
    synthetic = bool(base.synthetic_data_used)
    result = {**FLAGS, 'schema_version': 'clean6.sensor_model_v21.case.v1', 'protocol_id': 'SENSOR_MODEL_V2_1',
              'provider_family': STAGE_NAME, 'case_id': case_id, 'degradation_type_id': tid,
              'dataset_id': 'BY2', 'data_mode': 'synthetic_test' if synthetic else 'real' if tid == 'CLEAN' else 'semisynthetic',
              'synthetic_data_used': synthetic, 'semisynthetic_data_used': not synthetic and tid != 'CLEAN',
              'controlled_degradation_applied': tid != 'CLEAN',
              'case_root': str(root), 'providers': providers, 'GNSS15_projection': projection,
              'audit_payloads': audit_payloads, 'base_provider_pins': base.providers,
              'auxiliary_source_pins': base.auxiliary_roles, 'raw_input_hashes': dict(base.bundle.raw_input_hashes),
              'raw_source_hashes': base_bundle['raw_source_hashes'], 'provider_hashes': {k: v['sha256'] for k, v in providers.items()},
              'a1_association': base.a1_audit, 'components': components, 'semantics': semantics,
              'code_commit': code_commit, 'config_hash': config_hash, 'case_meta': case,
              'sensor_model_group_hash': v21_contract['sensor_model_group_hash'], 'semantic_equivalence': evidence,
              'runtime_contract': {'gnss_columns': 18, 'gnss_row_count': len(rows),
                  'position_valid_count': sum(int(r[15]) for r in rows), 'rv_valid_count': sum(int(r[16]) for r in rows),
                  'a1_valid_count': sum(int(r[17]) for r in rows), 'faulted_timing_union': tid == 'D57'},
              'solver_execution_count': 0, 'evaluator_execution_count': 0}
    write_json(root/'PROVIDER_VALIDATION.json', evidence)
    _seal(root, result)
    return result
