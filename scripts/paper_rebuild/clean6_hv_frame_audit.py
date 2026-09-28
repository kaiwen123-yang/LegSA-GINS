#!/usr/bin/env python3
"""P-11b observation-only frame hypotheses; never materialize solver providers."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

import numpy as np
import yaml

from clean6_hv_prior_residual_stats import Inputs, csv_data, heading_support, nearest, stats

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE / 'src'))
from legsa_gins.datasets.by2.go2_body_state_parser import _message_to_row

NAMES = ('H-A', 'H-B-median', 'H-B-sample', 'H-C')
AXES = ('N', 'E', 'along', 'right')
ROOT = '<CLEAN_ROOT>/stages/CLEAN6_HV_PRIOR_CALIBRATION/'
P11A_SHA = '3fce00c70e1d9ff52b0e930579075dcc6075b0d27dfeb5c913c6fc818b12d27e'


def wrap(x):
    return (x + np.pi) % (2*np.pi) - np.pi


def rotate(v, roll, pitch, yaw):
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    return np.column_stack((
        cy*cp*v[:, 0] + (cy*sp*sr-sy*cr)*v[:, 1] + (cy*sp*cr+sy*sr)*v[:, 2],
        sy*cp*v[:, 0] + (sy*sp*sr+cy*cr)*v[:, 1] + (sy*sp*cr-cy*sr)*v[:, 2],
        -sp*v[:, 0] + cp*sr*v[:, 1] + cp*cr*v[:, 2]))


def rotate_z(v, yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    return np.column_stack((c*v[:, 0]-s*v[:, 1], s*v[:, 0]+c*v[:, 1], v[:, 2]))


def body_fields(data):
    """Read only stamp, rpy, position, velocity; validate fixed samples against maintained parser."""
    messages = data.decode('utf-8').replace('\r\n', '\n').split('\n---')
    patterns = {
        'time': re.compile(r'^stamp:\n  sec: (\d+)\n  nanosec: (\d+)', re.M),
        **{name: re.compile(r'^'+indent+name+r':\n((?:'+indent+r'- [^\n]*(?:\n|$)){0,3})', re.M)
           for name, indent in (('rpy', '  '), ('position', ''), ('velocity', ''))}}
    values, source_indices = [], []
    for i, message in enumerate(messages):
        t = patterns['time'].search(message)
        if t is None:
            continue
        row = [int(t[1]) + int(t[2])*1e-9]
        for name in ('rpy', 'position', 'velocity'):
            found = patterns[name].search(message)
            elements = [float(line.strip()[2:]) for line in found[1].splitlines()] if found else []
            row.extend((elements + [np.nan]*3)[:3])
        values.append(row)
        source_indices.append(i)
    a = np.asarray(values)
    assert np.all(np.diff(a[:, 0]) >= 0)
    checked = sorted(set(np.linspace(0, len(a)-1, 16, dtype=int)))
    fields = ['timestamp', 'roll_rad', 'pitch_rad', 'yaw_rad'] + [f'go2_{name}_{i}' for name in ('position', 'velocity') for i in range(3)]
    for i in checked:
        reference = _message_to_row(messages[source_indices[i]].splitlines())
        expected = np.array([reference[k] if reference[k] is not None else np.nan for k in fields])
        assert np.array_equal(a[i], expected, equal_nan=True)
    return a, {'raw_stamped_messages': len(a), 'maintained_parser_checked_indices': [int(i) for i in checked],
               'all_checked_fields_identical': True}


def describe(x):
    out = stats(x)
    if len(x):
        out.update(median=float(np.median(x)), p05=float(np.quantile(x, .05)))
    return out


def speed_bins(speed):
    return {'lt_0_3': speed < .3, '0_3_to_0_8': (speed >= .3) & (speed <= .8), 'gt_0_8': speed > .8}


def regression(x, y):
    if len(x) < 2 or np.ptp(x) == 0:
        return {'status': 'UNAVAILABLE', 'n': len(x)}
    slope, intercept = np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), y, rcond=None)[0]
    origin = np.dot(x, y)/np.dot(x, x)
    return {'n': len(x), 'slope': float(slope), 'intercept': float(intercept),
            'through_origin_slope': float(origin), 'pearson_r': float(np.corrcoef(x, y)[0, 1]),
            'x_std': float(np.std(x, ddof=1))}


def direction_diagnostics(raw, window):
    t, rp, pos, vel = raw[:, 0], raw[:, 1:4], raw[:, 4:7], raw[:, 7:10]
    dt0, dt1 = np.diff(t)[:-1], np.diff(t)[1:]
    dt = t[2:] - t[:-2]
    dp = np.divide(pos[2:]-pos[:-2], dt[:, None], out=np.full_like(pos[1:-1], np.nan), where=dt[:, None] > 0)
    v = vel[1:-1]
    forward = rotate(np.tile([1., 0., 0.], (len(v), 1)), *rp[1:-1].T)
    world_v_if_body = rotate(v, *rp[1:-1].T)
    valid = ((t[:-2] >= window[0]) & (t[2:] <= window[1]) & (dt0 > 0) & (dt1 > 0)
             & (dt0 <= .1) & (dt1 <= .1) & np.isfinite(dp).all(axis=1)
             & np.isfinite(v).all(axis=1) & np.isfinite(forward).all(axis=1))
    vn, dn = np.linalg.norm(v[:, :2], axis=1), np.linalg.norm(dp[:, :2], axis=1)
    valid &= (vn > 1e-6) & (dn > 1e-6)
    moving = valid & (vn >= .3) & (dn >= .3)
    angles = lambda a, b: np.rad2deg(np.arccos(np.clip(np.sum(a*b, axis=1)/(np.linalg.norm(a, axis=1)*np.linalg.norm(b, axis=1)), -1, 1)))
    result = {}
    for name, mask in (('all_nonzero', valid), ('moving_ge_0_3_both', moving)):
        result[name] = {
            'n': int(mask.sum()),
            'velocity_vs_position_difference_horizontal_deg': describe(angles(v[mask, :2], dp[mask, :2])),
            'velocity_vs_rpy_forward_horizontal_deg': describe(angles(v[mask, :2], forward[mask, :2])),
            'velocity_vs_fixed_body_plus_x_horizontal_deg': describe(angles(v[mask, :2], np.tile([1., 0.], (int(mask.sum()), 1)))),
            'rpy_rotated_velocity_vs_position_difference_horizontal_deg': describe(angles(world_v_if_body[mask, :2], dp[mask, :2])),
            'rpy_rotated_velocity_vs_rpy_forward_horizontal_deg': describe(angles(world_v_if_body[mask, :2], forward[mask, :2])),
            'velocity_vs_position_difference_3d_deg': describe(angles(v[mask], dp[mask])),
            'velocity_vs_rpy_forward_3d_deg': describe(angles(v[mask], forward[mask]))}
    return result


def slot_acf(times, values, blocks, width=.02):
    """Same pair normalization as P-11a, using prefix sums instead of materialized pairs."""
    z = values - values.mean(axis=0)
    prefix = np.vstack((np.zeros(z.shape[1]), np.cumsum(z, axis=0)))
    prefix2 = np.vstack((np.zeros(z.shape[1]), np.cumsum(z*z, axis=0)))
    block_end = np.searchsorted(blocks, blocks, side='right')
    base = np.arange(len(times))

    def bound(lag):
        j = np.searchsorted(times, times+lag)
        prev = np.maximum(j-1, 0)
        j -= ((j > 0) & (times[prev]-times >= lag))
        cur = np.minimum(j, len(times)-1)
        j += ((j < len(times)) & (times[cur]-times < lag))
        return np.minimum(np.maximum(j, base+1), block_end)

    found = [None]*values.shape[1]
    at_one = None
    previous_positive = [0.]*values.shape[1]
    previous = bound(0.)
    slots = []
    limit = int(np.ceil((times[-1]-times[0])/width)) + 1
    for k in range(limit):
        upper = bound((k+1)*width)
        counts = upper-previous
        right = prefix[upper]-prefix[previous]
        right2 = prefix2[upper]-prefix2[previous]
        pairs = int(counts.sum())
        numerator = np.sum(z*right, axis=0)
        denominator = np.sqrt(np.sum(counts[:, None]*z*z, axis=0)*np.sum(right2, axis=0))
        rho = np.divide(numerator, denominator, out=np.full(z.shape[1], np.nan), where=(denominator > 0) & (pairs >= 20))
        if k == 50:
            at_one = {'slot_s': [1., 1.02], 'pair_count': pairs, 'rho': [float(x) if np.isfinite(x) else None for x in rho]}
        for a, value in enumerate(rho):
            if found[a] is None and np.isfinite(value):
                if value <= 0:
                    found[a] = {'slot_s': [k*width, (k+1)*width], 'rho': float(value),
                                'pair_count': pairs, 'previous_positive_slot_mid_s': previous_positive[a]}
                else:
                    previous_positive[a] = (k+.5)*width
        slots.append({'slot_s': [k*width, (k+1)*width], 'pair_count': pairs,
                      'rho': [float(x) if np.isfinite(x) else None for x in rho]})
        previous = upper
        if all(x is not None for x in found) and at_one is not None:
            break
    return {'at_1_s': at_one, 'first_nonpositive': found, 'searched_to_s': (k+1)*width, 'slots': slots}


def run_sequence(inputs, contract, prior, dataset):
    spec, old = contract['sequences'][dataset], prior['sequences'][dataset]
    provider_root = f'<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/{dataset}/'
    def pinned_previous(path):
        return inputs.read(path, prior['input_files'][path]['sha256'])
    cal = json.loads(pinned_previous(provider_root+'CALIBRATED_PROVIDER_BUNDLE.json'))
    assert spec['window_seconds'] == old['window_seconds'] and spec['base_time'] == old['base_time']
    assert cal['audit']['window_seconds'] == old['window_seconds']
    gnss = np.loadtxt(io.BytesIO(pinned_previous(provider_root+'CALIBRATED_GNSS.gnss')))
    rows = csv_data(pinned_previous(provider_root+'GO2_HORIZONTAL_VELOCITY_PRIOR.csv'))
    ht = np.array([float(r['time']) for r in rows])
    frozen = np.array([[float(r['vn']), float(r['ve'])] for r in rows])
    lock = {r['relative_path']: r['sha256'] for r in csv_data(inputs.pin(spec['raw_lock']))}
    body = spec['raw_inputs']['body']
    assert lock[body['path'].removeprefix('<RAW_ROOT>/')] == body['sha256']
    assert cal['raw_source_hashes']['body']['sha256'] == body['sha256']
    print(dataset+': read raw Go2 stamp/rpy/position/velocity', flush=True)
    raw, parser_audit = body_fields(inputs.pin(body))
    raw[:, 0] -= spec['base_time']
    complete = np.isfinite(raw[:, [0, 1, 2, 3, 7, 8, 9]]).all(axis=1)
    complete_raw = raw[complete]
    assert len(complete_raw) == len(ht)
    assert np.max(abs(complete_raw[:, 0]-ht)) < 1e-9
    rpy, v = complete_raw[:, 1:4], complete_raw[:, 7:10]
    hc_reconstructed = rotate(v, *rpy.T)
    parity_error = float(np.max(abs(hc_reconstructed[:, :2]-frozen)))
    assert parity_error < 1e-12
    g = gnss[gnss[:, 16] == 1]
    pt = np.rint(g[:, 0]*1000)/1000.
    a = gnss[gnss[:, 17] == 1]
    at, ay = np.rint(a[:, 0]*1000)/1000., np.unwrap(np.deg2rad(a[:, 13]))
    assert np.all(np.diff(pt) > 0) and np.all(np.diff(at) > 0)
    window = np.array(spec['window_seconds'])
    window_mask = (ht >= window[0]) & (ht <= window[1])
    support, gap, block = heading_support(ht, at)
    idx = nearest(pt, ht)
    keep = window_mask & support & (abs(ht-pt[idx]) <= .03)
    assert int(keep.sum()) == old['n']
    full_yaw = np.interp(ht, at, ay)
    delta = wrap(full_yaw-rpy[:, 2])
    median_mask = window_mask & support
    delta_median = float(wrap(np.median(np.unwrap(delta[median_mask]))))
    t, rpy, v, yaw = ht[keep], rpy[keep], v[keep], full_yaw[keep]
    pvt = g[idx[keep], 7:9]
    speed, norm3, norm2 = np.linalg.norm(pvt, axis=1), np.linalg.norm(v, axis=1), np.linalg.norm(v[:, :2], axis=1)
    bins = speed_bins(speed)
    nonzero = speed > 1e-6
    ratio3 = np.divide(norm3, speed, out=np.full_like(speed, np.nan), where=nonzero)
    ratio2 = np.divide(norm2, speed, out=np.full_like(speed, np.nan), where=nonzero)
    magnitude = {'all_nonzero_PVT': {'norm3_over_PVT_H': describe(ratio3[nonzero]), 'normXY_over_PVT_H': describe(ratio2[nonzero])},
                 'ratio_undefined_PVT_le_1e_6_count': int((~nonzero).sum()),
                 'moving_PVT_ge_0_3': {'norm3_over_PVT_H': describe(ratio3[speed >= .3]), 'normXY_over_PVT_H': describe(ratio2[speed >= .3])},
                 'bins': {k: {'norm3_over_PVT_H': describe(ratio3[m & nonzero]), 'normXY_over_PVT_H': describe(ratio2[m & nonzero]),
                              'total_n': int(m.sum())} for k, m in bins.items()}}
    # FLU -> FRD: S=diag(1,-1,-1). Euler conversion gives roll_FRD=roll_FLU, pitch_FRD=-pitch_FLU.
    ha = rotate(v*np.array([1., -1., -1.]), rpy[:, 0], -rpy[:, 1], yaw)
    hb_median = rotate_z(v, delta_median)
    hb_sample = rotate_z(v, delta[keep])
    for transformed in (ha, hb_median, hb_sample):
        assert np.max(abs(np.linalg.norm(transformed, axis=1)-norm3)) < 1e-12
    hypotheses = dict(zip(NAMES, (ha[:, :2], hb_median[:, :2], hb_sample[:, :2], frozen[keep])))
    residual_arrays, results = [], {}
    c, s = np.cos(yaw), np.sin(yaw)
    for name, velocity in hypotheses.items():
        residual = velocity-pvt
        components = np.column_stack((residual, c*residual[:, 0]+s*residual[:, 1], -s*residual[:, 0]+c*residual[:, 1]))
        residual_arrays.append(components)
        results[name] = {'n': len(t), 'axes_mps': {a: stats(components[:, i]) for i, a in enumerate(AXES)},
                         'sigma_HV_mps': float(np.sqrt(np.mean(np.var(residual, axis=0, ddof=1)))),
                         'mean_NE_norm_mps': float(np.linalg.norm(residual.mean(axis=0))),
                         'mean_along_right_norm_mps': float(np.linalg.norm(components[:, 2:].mean(axis=0))),
                         'bins': {k: {a: stats(components[m, i]) for i, a in enumerate(AXES)} for k, m in bins.items()},
                         'horizontal_speed_OLS_vs_PVT': regression(speed, np.linalg.norm(velocity, axis=1))}
    for i, axis in enumerate(AXES):
        original_axis = ('N', 'E', 'along_heading', 'right_lateral')[i]
        for metric in ('mean', 'std'):
            assert abs(results['H-C']['axes_mps'][axis][metric]-old['axes_mps'][original_axis][metric]) < 1e-12
    print(dataset+': four hypotheses, '+str(len(t))+' matched samples; actual-lag ACF', flush=True)
    acf = slot_acf(t, np.column_stack(residual_arrays), block[keep])
    for h, name in enumerate(NAMES):
        results[name]['acf_at_1_s'] = dict(zip(AXES, acf['at_1_s']['rho'][4*h:4*h+4]))
        results[name]['acf_first_nonpositive'] = dict(zip(AXES, acf['first_nonpositive'][4*h:4*h+4]))
        results[name]['acf_1s_pair_count'] = acf['at_1_s']['pair_count']
    for i, axis in enumerate(('N', 'E', 'along_heading', 'right_lateral')):
        assert abs(results['H-C']['acf_at_1_s'][AXES[i]]-old['acf'][axis]['rho_near_1_s']) < 1e-9
    slopes = {label: {'norm3_vs_PVT_H': regression(speed[m], norm3[m]),
                      'normXY_vs_PVT_H': regression(speed[m], norm2[m]),
                      'norm3_ratio_vs_PVT_H': regression(speed[m & nonzero], ratio3[m & nonzero])}
              for label, m in (('all', np.ones(len(t), bool)), ('moving_ge_0_3', speed >= .3))}
    rankings = {
        'mean_NE_closest_zero': sorted(NAMES, key=lambda h: results[h]['mean_NE_norm_mps']),
        'mean_along_right_closest_zero': sorted(NAMES, key=lambda h: results[h]['mean_along_right_norm_mps']),
        'sigma_HV_smallest': sorted(NAMES, key=lambda h: results[h]['sigma_HV_mps']),
        'absolute_1s_acf_smallest_by_axis': {a: sorted(NAMES, key=lambda h: abs(results[h]['acf_at_1_s'][a])) for a in AXES},
        'first_nonpositive_shortest_by_axis': {a: sorted(NAMES, key=lambda h: results[h]['acf_first_nonpositive'][a]['slot_s'][0]
                                                       if results[h]['acf_first_nonpositive'][a] else float('inf')) for a in AXES}}
    return {'dataset': dataset, 'window_seconds': spec['window_seconds'], 'n': len(t), 'magnitude': magnitude,
            'internal_direction': direction_diagnostics(raw, window), 'hypotheses': results,
            'magnitude_regressions': slopes, 'rankings': rankings,
            'delta_yaw': {'median_rad': delta_median, 'median_deg': float(np.rad2deg(delta_median)),
                          'median_sample_count': int(median_mask.sum()), 'matched_sample_count': len(t),
                          'circular_resultant_length': float(abs(np.mean(np.exp(1j*delta[median_mask])))),
                          'wrapped_sample_deg': describe(np.rad2deg(delta[median_mask]))},
            'acf': acf,
            'audit': {'parser': parser_audit, 'raw_vs_frozen_HV_max_abs_difference_mps': parity_error,
                      'P11a_HC_sample_and_mean_std_identity': True, 'P11a_HC_1s_acf_identity_atol_1e_9': True,
                      'same_iTOW_PVT_and_A1_identity_reused_from_hash_verified_P11a': True,
                      'A1_gap_matched_rejection_count': int((window_mask & gap & (abs(ht-pt[idx]) <= .03)).sum()),
                      'all_hypotheses_identical_sample_set': True, 'rotation_norm_preservation': True}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paths', type=Path, required=True)
    parser.add_argument('--code-commit', required=True)
    args = parser.parse_args()
    paths = yaml.safe_load(args.paths.read_text())['paths']
    inputs = Inputs(paths)
    output = inputs.resolve(ROOT)
    assert output.is_dir()
    opened = set()

    def guard(event, arguments):
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'):
            raise RuntimeError('No child processes in frame audit')
        if event != 'open' or not isinstance(arguments[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(arguments[0])).absolute()
        if p.name.lower().startswith(('trace_', 'trace.')) or p.suffix.lower() in ('.bag', '.fpl', '.nav', '.zip'):
            raise RuntimeError('Forbidden input')
        flags = arguments[2] or 0
        writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        if writing and p not in {output/'HV_FRAME_AUDIT.json', output/'HV_FRAME_AUDIT.md'}:
            raise RuntimeError('Write outside named audit outputs')
        if not writing and any(p.is_relative_to(inputs.roots[k]) for k in ('<RAW_ROOT>', '<CLEAN_ROOT>')):
            if p not in inputs.allowed:
                raise RuntimeError('Non-allowlisted observation input')
            opened.add(inputs.alias(p))

    sys.addaudithook(guard)
    prior = json.loads(inputs.read(ROOT+'HV_PRIOR_RESIDUAL_STATS.json', P11A_SHA))
    contract_path = '<CODE_ROOT>/configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml'
    contract = yaml.safe_load(inputs.read(contract_path, prior['input_files'][contract_path]['sha256']))
    sequences = {s: run_sequence(inputs, contract, prior, s) for s in ('BY2', 'BY2H', 'BY2O')}
    result = {'schema_version': 'paper_rebuild.clean6.hv_frame_audit.v1', 'task': 'P-11b',
              'status': 'COMPUTED_OBSERVATION_ONLY_AUDIT_HUMAN_DECISION_PENDING', 'code_commit': args.code_commit,
              'config_hash': prior['input_files'][contract_path]['sha256'],
              'data_mode': 'real_three_sequence_frozen_observation_frame_audit',
              'synthetic_data_used': False, 'semisynthetic_data_used': False, 'trace_used_online': False,
              'trace_read_count': 0, 'solver_invocations': 0, 'evaluator_invocations': 0, 'provider_generations': 0,
              'receiver_imu_as_body_imu': False, 'final_v23_output_solver_input': False, 'LegSA_output_solver_input': False,
              'per_case_tuning': False, 'output_only_correction': False, 'epoch_deleted_for_metric': False,
              'old_runtime_input_count': 0, 'contracts_changed': False, 'parameters_changed': False,
              'definitions': {
                  'alignment': 'P-11a identical HV samples: nearest frozen same-iTOW PVT <=0.03 s; closed windows; A1 unwrap/interpolation, no extrapolation, open gaps >1.2 s excluded',
                  'H-A': 'Assume raw velocity body FLU: Rz(A1_yaw) Ry(-Go2_pitch) Rx(Go2_roll) diag(1,-1,-1) v; FLU-to-FRD coordinate conversion, not a fitted sign',
                  'H-B-median': 'Rz(median(unwrap(wrap(A1_yaw-Go2_yaw))))) v; median uses all window HV samples with A1 support, before PVT matching',
                  'H-B-sample': 'Rz(wrap(A1_yaw-Go2_yaw)) v at each retained sample; no roll/pitch rotation',
                  'H-C': 'Frozen CSV vn/ve unchanged; independently reproduced from raw Go2 Rz(yaw) Ry(pitch) Rx(roll) v within 1e-12 m/s',
                  'magnitude': 'Primary |v_go2| is full 3-D Euclidean norm; also report raw XY norm. Compare to PVT horizontal speed; denominator <=1e-6 m/s undefined, counted separately',
                  'bins': 'PVT horizontal speed <0.3, [0.3,0.8], >0.8 m/s; report all bins, no low-speed trimming from residual statistics',
                  'direction': 'Raw Go2 log only, full frozen window. Central position difference / actual elapsed time; both adjacent dt in (0,0.1] s. Horizontal directions require both norms >1e-6; primary moving subset both >=0.3 m/s',
                  'forward': 'Rz(Go2_yaw) Ry(Go2_pitch) Rx(Go2_roll) [1,0,0]; compare in odom numeric axes. Alignment with this world-expressed forward axis does not itself establish that raw velocity is body-expressed; fixed body +x comparison also reported',
                  'std': 'ddof=1; sigma_HV=sqrt((var_N+var_E)/2), no PVT noise subtraction; all four hypotheses have the same sample mask',
                  'components': 'along=cos(A1)*rN+sin(A1)*rE; right=-sin(A1)*rN+cos(A1)*rE',
                  'ACF': 'Same P-11a actual-lag pair normalization, globally demeaned, 0.02 s slots, >=20 pairs, no resampling or gap compression; report [1,1.02) s and first nonpositive slot. Prefix sums equal pair sums; stop after all crossings and 1 s observed',
                  'ranking': 'Report separate rankings for mean-vector norms, sigma_HV, absolute 1s ACF by axis, first nonpositive lag by axis; do not invent a weighted combined score',
                  'regression': 'OLS |v_go2|=slope*|v_PVT,H|+intercept and through-origin slope; also literal ratio-versus-PVT-speed slope. All and PVT>=0.3 subsets. Full 3-D norm slopes are invariant under rotations; hypothesis-specific horizontal slopes also reported',
                  'decision': 'Input-only descriptive ranking, not solver validation or authorization to replace frozen providers'},
              'sequences': sequences, 'input_files': inputs.ledger,
              'file_access_guard': {'status': 'PASS', 'observation_input_paths_opened': sorted(opened),
                                    'forbidden_input_opens': 0, 'subprocess_launches': 0},
              'process_sha256': {str(Path(m.__file__).resolve().relative_to(CODE)): hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                                 for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                                 and Path(m.__file__).suffix == '.py' and Path(m.__file__).resolve().is_relative_to(CODE)}}
    with (output/'HV_FRAME_AUDIT.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print('WROTE HV_FRAME_AUDIT.json', flush=True)


if __name__ == '__main__':
    main()
