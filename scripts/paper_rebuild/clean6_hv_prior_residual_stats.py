#!/usr/bin/env python3
"""P-11a: frozen-input residual statistics only; no provider/solver/evaluator calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys

import numpy as np
import yaml

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE / 'src'))
from legsa_gins.paper_rebuild.clean5_parity.input_audit import decode_receiver, epoch_key, stamp

STAGE = 'CLEAN6_HV_PRIOR_CALIBRATION'
SEQUENCES = ('BY2', 'BY2H', 'BY2O')
ROLES = ('gnsspath', 'go2_horizontal_velocity_prior_path')


def nearest(times, targets):
    """Nearest observation, earlier epoch on an exact tie; no interpolation."""
    right = np.clip(np.searchsorted(times, targets), 0, len(times) - 1)
    left = np.maximum(right - 1, 0)
    return np.where(abs(targets - times[left]) <= abs(targets - times[right]), left, right)


def heading_support(times, a1_times):
    j = np.clip(np.searchsorted(a1_times, times, side='right') - 1, 0, len(a1_times) - 2)
    gaps = np.diff(a1_times) > 1.2
    inside_gap = gaps[j] & (times > a1_times[j]) & (times < a1_times[j + 1])
    supported = (times >= a1_times[0]) & (times <= a1_times[-1]) & ~inside_gap
    # Distinct continuous A1 support blocks; ACF pairs never bridge a long gap.
    block = np.searchsorted(a1_times[1:][gaps], times, side='right')
    return supported, inside_gap, block


def stats(values):
    x = np.asarray(values, float)
    if not len(x):
        return {'n': 0, 'status': 'UNAVAILABLE_EMPTY_BIN'}
    assert np.isfinite(x).all()
    return dict(n=len(x), mean=float(x.mean()), std=float(x.std(ddof=1)) if len(x) > 1 else None,
                p95_abs=float(np.quantile(abs(x), .95)), max_abs=float(abs(x).max()),
                p95_signed=float(np.quantile(x, .95)), max_signed=float(x.max()),
                min_signed=float(x.min()), rms_uncentered=float(np.sqrt(np.mean(x*x))))


def physical_acf(times, values, blocks, width=.02, horizon=None):
    """Slotted autocorrelation on actual time differences, without resampling.

    Globally demean each axis. For each positive-lag slot use the normalized
    sum of pair products (Cauchy normalization); retain missing slots as null.
    Multiple HV samples assigned to one PVT observation remain distinct.
    """
    z = values - values.mean(axis=0)
    if horizon is None:
        horizon = float(times[-1] - times[0]) + width
    bins = int(np.ceil(horizon / width))
    sums = np.zeros((bins, z.shape[1]))
    sqleft = np.zeros_like(sums)
    sqright = np.zeros_like(sums)
    counts = np.zeros(bins, dtype=np.int64)
    elapsed = np.zeros(bins)
    offsets = int(np.max(np.searchsorted(times, times + horizon) - np.arange(len(times))))
    for k in range(1, offsets):
        dt = times[k:] - times[:-k]
        mask = (dt > 0) & (dt < horizon) & (blocks[k:] == blocks[:-k])
        b = np.floor(dt[mask] / width).astype(int)
        if not len(b):
            continue
        counts += np.bincount(b, minlength=bins)
        elapsed += np.bincount(b, weights=dt[mask], minlength=bins)
        left, right = z[:-k][mask], z[k:][mask]
        for a in range(z.shape[1]):
            sums[:, a] += np.bincount(b, weights=left[:, a]*right[:, a], minlength=bins)
            sqleft[:, a] += np.bincount(b, weights=left[:, a]**2, minlength=bins)
            sqright[:, a] += np.bincount(b, weights=right[:, a]**2, minlength=bins)
    result = {}
    for a, name in enumerate(('N', 'E', 'along_heading', 'right_lateral')):
        denom = np.sqrt(sqleft[:, a]*sqright[:, a])
        good = (counts >= 20) & (denom > 0)
        rho = np.divide(sums[:, a], denom, out=np.full(bins, np.nan), where=good)
        first = np.flatnonzero(good & (rho <= 0))
        index = int(first[0]) if len(first) else None
        previous = np.flatnonzero(good[:index]) if index is not None else []
        summary = {
            'first_nonpositive_lag_s': float(elapsed[index]/counts[index]) if index is not None else None,
            'first_nonpositive_slot_s': [index*width, (index+1)*width] if index is not None else None,
            'previous_positive_lag_s': float(elapsed[previous[-1]]/counts[previous[-1]]) if len(previous) else 0.,
            'status': 'OBSERVED_FIRST_NONPOSITIVE_SLOT' if index is not None else 'NOT_OBSERVED_WITHIN_AVAILABLE_LAGS',
            'search_horizon_s': horizon,
            'unobserved_slots_before_first_nonpositive': int((~good[:index]).sum()) if index is not None else None,
            'rho_near_0_2_s': float(rho[10]) if good[10] else None,
            'rho_near_1_s': float(rho[50]) if good[50] else None,
            'first_observed_positive_lag_rho': float(rho[np.flatnonzero(good)[0]]),
            'slots': [{'lag_start_s': i*width, 'lag_end_s': (i+1)*width,
                       'mean_actual_lag_s': float(elapsed[i]/counts[i]) if counts[i] else None,
                       'pair_count': int(counts[i]), 'rho': float(rho[i]) if good[i] else None}
                      for i in range(bins)]}
        result[name] = summary
    return result


class Inputs:
    def __init__(self, paths):
        self.roots = {f'<{k.upper()}>': Path(v).resolve() for k, v in paths.items()
                      if k in ('code_root', 'raw_root', 'clean_root')}
        self.ledger = {}
        self.allowed = set()

    def resolve(self, value):
        for alias, root in self.roots.items():
            value = str(value).replace(alias, str(root))
        p = Path(value)
        if not p.is_absolute() or '<' in str(p) or any(x.is_symlink() for x in (p, *p.parents)):
            raise ValueError('Unresolved or symlink input')
        if p.name.lower().startswith(('trace_', 'trace.')) or p.suffix.lower() in ('.bag', '.fpl', '.nav', '.zip'):
            raise ValueError('Forbidden input role')
        return p

    def alias(self, path):
        for alias, root in self.roots.items():
            if path.is_relative_to(root):
                return alias + '/' + path.relative_to(root).as_posix()
        raise ValueError('Input outside registered roots')

    def read(self, value, expected=None):
        p = self.resolve(value)
        self.allowed.add(p)
        data = p.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if expected is not None and expected != digest:
            raise ValueError('Hash mismatch: ' + self.alias(p))
        key = self.alias(p)
        record = {'sha256': digest, 'bytes': len(data), 'pinned_sha256_verified': expected is not None}
        if key in self.ledger:
            assert self.ledger[key]['sha256'] == digest
            record['pinned_sha256_verified'] |= self.ledger[key]['pinned_sha256_verified']
        self.ledger[key] = record
        return data

    def pin(self, spec):
        return self.read(spec['path'], spec['sha256'])


def csv_data(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))


def sequence(inputs, contract, sensor, dataset):
    spec = contract['sequences'][dataset]
    base = spec['base_time']
    start, end = spec['window_seconds']
    original = json.loads(inputs.pin(spec['source_bundle']))
    cal_path = f'<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/{dataset}/CALIBRATED_PROVIDER_BUNDLE.json'
    cal = json.loads(inputs.read(cal_path))
    assert cal['source_provider_bundle'] == spec['source_bundle']
    assert cal['audit']['window_seconds'] == [start, end] and cal['audit']['base_time'] == base
    assert not any(cal[k] for k in ('synthetic_data_used', 'semisynthetic_data_used', 'trace_used_online'))
    data = {}
    for role in ROLES:
        pin = cal['variants']['V2s']['providers'][role]
        assert pin['sha256'] == original['variants'][spec['source_variant']]['providers'][role]['sha256']
        assert any(r['key'] == role and r['byte_equal'] and r['output_sha256'] == pin['sha256']
                   for r in cal['audit']['provider_copy_ledger'])
        data[role] = inputs.pin(pin)
    # Validate only the observation roles actually read; never traverse all raw payloads.
    locked = {r['relative_path']: r['sha256'] for r in csv_data(inputs.pin(spec['raw_lock']))}
    for role in ('status', 'gnss1'):
        pin = spec['raw_inputs'][role]
        assert locked[pin['path'].removeprefix('<RAW_ROOT>/')] == pin['sha256']
        assert cal['raw_source_hashes'][role]['sha256'] == pin['sha256']
    status = csv_data(inputs.pin(spec['raw_inputs']['status']))
    inputs.pin(spec['raw_inputs']['gnss1'])
    _, pvt = decode_receiver(inputs.resolve(spec['raw_inputs']['gnss1']['path']))
    weeks = {int(float(r['time_gps_wno'])) for r in status}
    assert len(weeks) == 1
    week = weeks.pop()
    # Integer iTOW identity; reduce to relative milliseconds before float conversion.
    relative_ms_offset = int((315964800 + week*604800 - 18 - base)*1000)
    keys = sorted(pvt)
    pvt_ms = np.array(keys, np.int64) + relative_ms_offset
    pt = pvt_ms/1000.
    pv = np.array([pvt[k]['velocity_mps'][:2] for k in keys])
    gnss = np.loadtxt(io.BytesIO(data['gnsspath']), ndmin=2)
    assert gnss.shape[1] == 18 and np.isfinite(gnss).all()
    gm = {round(r[0]*1000): r for r in gnss}
    assert len(gm) == len(gnss)
    for k, ms in zip(keys, pvt_ms):
        row = gm[int(ms)]
        assert row[16] == 1 and np.allclose(row[7:10], pvt[k]['velocity_mps'], atol=1e-12, rtol=0)
    assert sum(gnss[:, 16] == 1) == len(keys)
    # Independently check that GNSS18 yaw-valid epochs are the frozen A1 identities.
    sm = {round(stamp(r, 'header.stamp.')*1000): epoch_key(r) for r in status}
    assert len(sm) == len(status)
    if dataset == 'BY2':
        a1_rows = csv_data(inputs.pin(sensor['calibration']['inputs']['a1']))
        a1_ms = [sm[round(float(r['source_timestamp'])*1000)] + relative_ms_offset for r in a1_rows]
        for r, ms in zip(a1_rows, a1_ms):
            if ms in gm:
                assert abs((gm[ms][13] - float(r['body_yaw_ned_deg']) + 180) % 360 - 180) < 1e-6
    else:
        gate = json.loads(inputs.pin(original['audit']['source_specs']['a1_gate']))
        a1_ms = [sm[round((r['time'] + base)*1000)] + relative_ms_offset for r in gate['per_epoch']]
    assert {ms for ms in a1_ms if ms in gm} == {round(r[0]*1000) for r in gnss if r[17] == 1}
    # Omitted source endpoints must be outside the analysis window plus the 1.2 s support margin.
    assert all(ms in gm for ms in a1_ms if (start - 1.2)*1000 <= ms <= (end + 1.2)*1000)
    a1 = gnss[gnss[:, 17] == 1]
    at = np.rint(a1[:, 0]*1000)/1000.
    yaw = np.unwrap(np.deg2rad(a1[:, 13]))
    assert at[0] <= start and at[-1] >= end and np.all(np.diff(at) > 0)
    hv_rows = csv_data(data['go2_horizontal_velocity_prior_path'])
    assert {r['frame_candidate'] for r in hv_rows} == {'go2_velocity_as_body_flu_then_rotate_by_go2_attitude'}
    assert all(r['update_flag'] == 'True' for r in hv_rows)
    old_sigmas = {float(r[k]) for r in hv_rows for k in ('std_vn', 'std_ve')}
    cfg_pin = spec['original_configs']['A04']
    cfg = yaml.safe_load(inputs.read(cfg_pin['runtime_config'], cfg_pin['runtime_config_sha256']))
    assert len(old_sigmas) == 1 and cfg['go2_horizontal_velocity_prior_std_scale'] == 1.0
    assert cfg['go2_horizontal_velocity_adaptive_std_enabled'] is False
    ht = np.array([float(r['time']) for r in hv_rows])
    hv = np.array([[float(r['vn']), float(r['ve'])] for r in hv_rows])
    assert np.isfinite(hv).all() and np.all(np.diff(ht) > 0)
    idx = nearest(pt, ht)
    offset = ht - pt[idx]
    in_window = (ht >= start) & (ht <= end)
    matched = in_window & (abs(offset) <= .03)
    supported, in_gap, block = heading_support(ht, at)
    keep = matched & supported
    t, observed, reference = ht[keep], hv[keep], pv[idx[keep]]
    residual = observed - reference
    heading = np.interp(t, at, yaw)
    c, s = np.cos(heading), np.sin(heading)
    rotate = lambda v: np.column_stack((c*v[:, 0] + s*v[:, 1], -s*v[:, 0] + c*v[:, 1]))
    rb, vb, pb = rotate(residual), rotate(observed), rotate(reference)
    axes = {name: stats(v) for name, v in zip(('N', 'E', 'along_heading', 'right_lateral'),
                                            np.column_stack((residual, rb)).T)}
    speed = np.linalg.norm(reference, axis=1)
    bins = {name: {'N': stats(residual[m, 0]), 'E': stats(residual[m, 1])}
            for name, m in (('lt_0_3', speed < .3), ('0_3_to_0_8_inclusive', (speed >= .3) & (speed <= .8)),
                            ('gt_0_8', speed > .8))}
    sigma = float(np.sqrt(np.mean(np.var(residual, axis=0, ddof=1))))
    demeaned = float(np.sqrt(np.sum((residual - residual.mean(axis=0))**2)/(2*(len(t)-1))))
    assert abs(sigma - demeaned) < 1e-12
    assert abs(np.sum(residual**2) - np.sum(rb**2)) < 1e-8
    assert sum(v['N']['n'] for v in bins.values()) == len(t)
    ols = []
    for axis in range(2):
        design = np.column_stack((pb[:, axis], np.ones(len(t))))
        coef = np.linalg.lstsq(design, vb[:, axis], rcond=None)[0]
        ols.append({'slope': float(coef[0]), 'intercept_mps': float(coef[1]),
                    'pearson_r': float(np.corrcoef(pb[:, axis], vb[:, axis])[0, 1])})
    print(f'{dataset}: {len(t)} matched HV rows, calculating physical-lag ACF', flush=True)
    acf = physical_acf(t, np.column_stack((residual, rb)), block[keep])
    return {
        'dataset': dataset, 'data_mode': cal['data_mode'], 'window_seconds': [start, end], 'base_time': base,
        'n': len(t), 'axes_mps': axes, 'pvt_horizontal_speed_bins_mps': bins,
        'sigma_HV_mps': sigma, 'decision_references_mps': {
            'original_go2_horizontal_velocity_std_mps': old_sigmas.pop(),
            'along_heading_std': axes['along_heading']['std'], 'demeaned_NE_scalar_std': demeaned},
        'uncentered_NE_rms_mps': float(np.sqrt(np.mean(residual**2))),
        'descriptive_OLS_HV_component_vs_PVT_component': dict(zip(('along_heading', 'right_lateral'), ols)),
        'acf': acf,
        'alignment': {'provider_rows': len(ht), 'provider_rows_in_window': int(in_window.sum()),
                      'rejected_nearest_pvt_gt_0_03_s': int((in_window & ~matched).sum()),
                      'rejected_A1_gap_after_matching': int((matched & in_gap).sum()),
                      'rejected_A1_no_extrapolation_after_matching': int((matched & ~supported & ~in_gap).sum()),
                      'unique_PVT_epochs_matched': len(np.unique(idx[keep])),
                      'same_PVT_epoch_reused': len(t) - len(np.unique(idx[keep])),
                      'matched_time_offset_s': stats(offset[keep]),
                      'original_HV_median_dt_s': float(np.median(np.diff(ht))),
                      'A1_iTOW_gap_intervals_gt_1_2_s': [[float(a), float(b)] for a, b in zip(at[:-1], at[1:]) if b-a > 1.2],
                      'same_iTOW_PVT_vs_frozen_GNSS18_identity': True,
                      'A1_source_epoch_vs_GNSS18_yaw_valid_identity': True,
                      'CAL_HV_GNSS_byte_identity_to_original_V2s_or_V2': True}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paths', type=Path, required=True)
    parser.add_argument('--code-commit', required=True)
    args = parser.parse_args()
    paths = yaml.safe_load(args.paths.read_text())['paths']
    inputs = Inputs(paths)
    assert inputs.roots['<CODE_ROOT>'] == CODE
    output = inputs.roots['<CLEAN_ROOT>'] / 'stages' / STAGE
    output.mkdir(exist_ok=True)
    opened = set()

    def audit(event, arguments):
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'):
            raise RuntimeError('Process launch forbidden in P-11a calculation')
        if event != 'open' or not isinstance(arguments[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(arguments[0])).absolute()
        name = p.name.lower()
        if name.startswith(('trace_', 'trace.')) or p.suffix.lower() in ('.bag', '.fpl', '.nav', '.zip'):
            raise RuntimeError('Forbidden data read: ' + str(p))
        flags = arguments[2] or 0
        writing = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        if writing and not p.is_relative_to(output):
            raise RuntimeError('Write outside calculation root')
        if not writing and any(p.is_relative_to(inputs.roots[x]) for x in ('<RAW_ROOT>', '<CLEAN_ROOT>')):
            if p not in inputs.allowed:
                raise RuntimeError('Non-allowlisted data input')
            opened.add(inputs.alias(p))

    sys.addaudithook(audit)
    contract = yaml.safe_load(inputs.read('<CODE_ROOT>/configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml'))
    sensor = yaml.safe_load(inputs.pin(contract['sensor_contract']))
    for source in ('src/legsa_gins/paper_rebuild/providers.py',
                   'src/legsa_gins/go2_prior/go2_velocity_frame_review.py',
                   'src/legsa_gins/paper_rebuild/protocol.py'):
        inputs.read('<CODE_ROOT>/' + source)
    results = {s: sequence(inputs, contract, sensor, s) for s in SEQUENCES}
    result = {
        'schema_version': 'paper_rebuild.clean6.hv_prior_residual_stats.v1', 'task': 'P-11a',
        'status': 'COMPUTED_FROZEN_PROVIDER_STATISTICS_HUMAN_DECISION_PENDING',
        'code_commit': args.code_commit, 'data_mode': 'real_three_sequence_frozen_observation_residuals',
        'config_hash': inputs.ledger['<CODE_ROOT>/configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml']['sha256'],
        'synthetic_data_used': False, 'semisynthetic_data_used': False, 'trace_used_online': False,
        'trace_read_count': 0, 'solver_invocations': 0, 'evaluator_invocations': 0, 'provider_generations': 0,
        'receiver_imu_as_body_imu': False, 'final_v23_output_solver_input': False,
        'LegSA_output_solver_input': False, 'per_case_tuning': False, 'output_only_correction': False,
        'epoch_deleted_for_metric': False, 'old_runtime_input_count': 0,
        'contracts_changed': False, 'parameters_changed': False, 'decision': 'HUMAN_PENDING',
        'source_semantics': {
            'requested_parenthetical': 'Go2 roll/pitch plus A1 yaw',
            'actual_frozen_HV': 'Go2 raw roll/pitch/yaw; Rz(yaw) Ry(pitch) Rx(roll) on raw Go2 velocity; horizontal projection',
            'status': 'REQUEST_DESCRIPTION_DIFFERS_FROM_FROZEN_PROVIDER',
            'policy': 'Frozen provider retained; no A1 re-rotation or replacement provider generated',
            'A1_use_here': 'iTOW heading-gap exclusion and along/right horizontal residual projection only'},
        'definitions': {
            'residual': 'frozen HV [vn,ve] minus same-iTOW raw PVT [vN,vE], byte-value checked against V2s GNSS18',
            'alignment': 'Each closed-window HV sample to nearest PVT epoch <=0.03 s, earlier tie; no PVT interpolation or lag fitting',
            'A1': 'Status-header millisecond identity to iTOW, unwrap yaw then linearly interpolate, no extrapolation; exclude open gaps >1.2 s, retain measured endpoints',
            'std': 'Sample standard deviation, ddof=1, matching P-06; means removed independently per reported axis',
            'p95_and_max': 'Primary P95 and maximum are of absolute residual; signed P95/max/min also retained',
            'sigma_HV': 'sqrt((sample_variance_N + sample_variance_E)/2); single scalar; PVT noise NOT subtracted (conservative)',
            'demeaned_sigma': 'Identical to sigma_HV by definition with the same ddof; uncentered RMS reported separately',
            'heading_components': 'along=cos(A1)*rN+sin(A1)*rE; right=-sin(A1)*rN+cos(A1)*rE; horizontal heading frame, not full 3-D body rotation',
            'bins': 'PVT horizontal speed; <0.3, [0.3,0.8], >0.8 m/s; HV samples retain their original sample weight',
            'OLS': 'Descriptive HV_component = slope*PVT_component + intercept; no correction applied; correlated samples and both sensors noisy, not an identified sensor-only scale',
            'ACF': 'Actual-time positive-lag pairs in 0.02 s half-open slots over the available sequence span; globally demeaned, sum-products / sqrt(sum-left-squares*sum-right-squares); >=20 pairs; no resampling; never bridge >1.2 s A1 gaps',
            'ACF_zero': 'First observed nonpositive slot, reported by mean actual lag and full slot bounds; unsampled slots stay null, no claimed exact continuous crossing',
            'whiteness': 'Descriptive serial-correlation assessment, not a formal white-noise certification; repeated nearest-PVT assignments included'},
        'sequences': results,
        'input_files': inputs.ledger,
        'file_access_guard': {'status': 'PASS', 'external_input_paths_opened': sorted(opened),
                              'trace_bag_fpl_NAV_zip_opens': 0, 'subprocess_launches': 0},
        'process_sha256': {str(Path(m.__file__).resolve().relative_to(CODE)): hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                           for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                           and Path(m.__file__).suffix == '.py' and Path(m.__file__).resolve().is_relative_to(CODE)}}
    target = output / 'HV_PRIOR_RESIDUAL_STATS.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print('WROTE', target, flush=True)


if __name__ == '__main__':
    main()
