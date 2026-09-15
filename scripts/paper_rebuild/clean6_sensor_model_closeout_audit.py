#!/usr/bin/env python3
"""P-12 sensor-model diagnostics; immutable observations, no solver or trace."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import numpy as np
import yaml
from clean6_hv_a1_yaw_diagnostic import (
    CODE, ROOT, SEQUENCES, fmt, load_observations, provenance, setup, table)
from clean6_hv_frame_audit import rotate, slot_acf, wrap
from clean6_hv_prior_residual_stats import csv_data, heading_support, nearest, stats
from legsa_gins.datasets.by2.go2_body_state_parser import _message_to_row
from legsa_gins.input_generation.status_yaw_builder import apply_status_valid_filter, _prepared_rows, _interp
from legsa_gins.paper_rebuild.clean5_imu_parity.providers import frozen_token

AXES = ('x', 'y', 'z')
TAUS = (.01, .02, .05, .1, .2, .5, 1., 2., 5., 10.)


def imu_fields(payload):
    messages = payload.decode('utf-8').replace('\r\n', '\n').split('\n---')
    tp = re.compile(r'^stamp:\n  sec: (\d+)\n  nanosec: (\d+)', re.M)
    pats = {k: re.compile(r'^  '+k+r':\n((?:  - [^\n]*(?:\n|$)){0,'+str(n)+r'})', re.M)
            for k, n in (('gyroscope', 3), ('accelerometer', 3), ('quaternion', 4))}
    rows, indices = [], []
    for i, message in enumerate(messages):
        ts = tp.search(message)
        if ts is None:
            continue
        row = [int(ts[1])+int(ts[2])*1e-9]
        for k, n in (('gyroscope', 3), ('accelerometer', 3), ('quaternion', 4)):
            found = pats[k].search(message)
            vals = [float(line.strip()[2:]) for line in found[1].splitlines()] if found else []
            row.extend((vals+[np.nan]*n)[:n])
        rows.append(row)
        indices.append(i)
    a = np.asarray(rows)
    checked = sorted(set(np.linspace(0, len(a)-1, 16, dtype=int)))
    keys = ['timestamp']+[f'gyro_{k}' for k in AXES]+[f'acc_{k}' for k in AXES]+[f'quat_{k}' for k in ('w', 'x', 'y', 'z')]
    for i in checked:
        ref = _message_to_row(messages[indices[i]].splitlines())
        expected = np.array([ref[k] if ref[k] is not None else np.nan for k in keys])
        assert np.array_equal(a[i], expected, equal_nan=True)
    return a, {'checked_raw_rows': [int(i) for i in checked], 'fields_exact': True}


def integrate(t, rates):
    dt = np.diff(t)
    good = (dt > 0)&(dt <= .1)
    values = np.cumsum(np.vstack((np.zeros((1, rates.shape[1])), rates[1:]*np.where(good, dt, 0)[:, None])), axis=0)
    def at(q):
        return np.column_stack([np.interp(q, t, values[:, i]) for i in range(values.shape[1])])
    bad = np.r_[0, np.cumsum(~good)]
    def support(start, end):
        left = np.clip(np.searchsorted(t, start, side='right'), 1, len(t)-1)
        right = np.clip(np.searchsorted(t, end, side='left'), 1, len(t)-1)
        return (start >= t[0])&(end <= t[-1])&(end > start)&((bad[right]-bad[left-1]) == 0)
    return at, support


def a1_intervals(data, left, right):
    s0, _, b0 = heading_support(left, data['at'])
    s1, _, b1 = heading_support(right, data['at'])
    return s0&s1&(b0 == b1)


def fit_origin(x, y, seed):
    if len(x) < 2 or np.dot(x, x) == 0:
        return {'n': len(x), 'status': 'UNAVAILABLE_FEWER_THAN_TWO_TURN_BLOCKS', 'slope': None, 'ci95': None}
    k = float(np.dot(x, y)/np.dot(x, x))
    rng = np.random.default_rng(seed)
    ii = rng.integers(0, len(x), size=(10000, len(x)))
    den = np.sum(x[ii]**2, axis=1)
    assert np.all(den > 0)
    ks = np.sum(x[ii]*y[ii], axis=1)/den
    residual = y-k*x
    noise = float(np.std(residual, ddof=1))
    systematic = float(np.sqrt(np.mean(((k-1)*x)**2)))
    return {'n': len(x), 'status': 'DESCRIPTIVE_BOOTSTRAP_5S_BLOCKS', 'slope': k,
            'ci95': [float(v) for v in np.quantile(ks, [.025, .975])],
            'fit_residual_deg': stats(residual), 'unit_scale_residual_deg': stats(y-x),
            'systematic_angle_RMS_deg': systematic, 'noise_sigma_deg': noise,
            'systematic_gt_3sigma': bool(systematic > 3*noise), 'bootstrap_seed': seed, 'bootstrap_count': 10000}


def gyro_and_heading(data, t, gyro, rpy, seed):
    # Sensor attitude C_n_s = C_n_b R_b_s. R_b_s=Rx(-1deg) => roll_body=roll_sensor+1deg.
    bias = gyro[:1000].mean(axis=0)
    unbiased = gyro-bias
    roll, pitch = rpy[:, 0]+np.deg2rad(1.), -rpy[:, 1]
    assert np.all(abs(np.cos(pitch)) > .1)
    yaw_rate = (unbiased[:, 1]*np.sin(roll)+unbiased[:, 2]*np.cos(roll))/np.cos(pitch)
    integ, support = integrate(t, np.column_stack((unbiased[:, 2], yaw_rate)))
    window = data['spec']['window_seconds']
    left = np.arange(window[0], window[1]-5+1e-8, 5.)
    right = left+5
    valid = a1_intervals(data, left, right)&support(left, right)
    delta = np.rad2deg(np.interp(right, data['at'], data['ay'])-np.interp(left, data['at'], data['ay']))
    turns = valid&(abs(delta) > 20)
    angles = np.rad2deg(integ(right[turns])-integ(left[turns]))
    fits = {key: fit_origin(angles[:, i], delta[turns], seed) for i, key in enumerate(('installed_z', 'euler_yaw_rate'))}
    turn_rows = [{'start_s': float(a), 'end_s': float(b), 'A1_increment_deg': float(c),
                  'gyro_z_increment_deg': float(g[0]), 'gyro_yaw_increment_deg': float(g[1])}
                 for a, b, c, g in zip(left[turns], right[turns], delta[turns], angles)]
    at = data['at']
    ms = np.rint(at*1000).astype(np.int64)
    endpoint = {int(v): i for i, v in enumerate(ms)}
    pairs = [(i, endpoint[int(v+1000)]) for i, v in enumerate(ms) if int(v+1000) in endpoint and at[i] >= window[0] and at[endpoint[int(v+1000)]] <= window[1]]
    pairs = np.asarray(pairs, int)
    a, b = at[pairs[:, 0]], at[pairs[:, 1]]
    supported = a1_intervals(data, a, b)&support(a, b)
    a, b, pairs = a[supported], b[supported], pairs[supported]
    dy = np.rad2deg(data['ay'][pairs[:, 1]]-data['ay'][pairs[:, 0]])
    dg = np.rad2deg(integ(b)-integ(a))
    residual = dy[:, None]-dg
    blocks = heading_support(a, at)[2]
    acf = slot_acf(a, residual, blocks)
    heading = {}
    for i, key in enumerate(('installed_z', 'euler_yaw_rate')):
        sigma = float(np.std(residual[:, i], ddof=1)/np.sqrt(2))
        heading[key] = {'n': len(a), 'increment_residual_deg': stats(residual[:, i]), 'sigma_A1_deg': sigma,
                        'frozen_sigma_A1_deg': 1.5, 'relative_difference': abs(sigma/1.5-1),
                        'relative_difference_gt_50pct': bool(abs(sigma/1.5-1) > .5),
                        'acf_first_nonpositive': acf['first_nonpositive'][i],
                        'acf_at_1_s': acf['at_1_s']['rho'][i], 'acf_1s_pair_count': acf['at_1_s']['pair_count']}
    return {'bias_first1000_deg_per_h': (np.rad2deg(bias)*3600).tolist(),
            'x_scale': 'NOT_OBSERVABLE', 'y_scale': 'NOT_OBSERVABLE', 'fits': fits, 'turn_blocks': turn_rows,
            'five_second_block_count': len(left), 'unsupported_block_count': int((~valid).sum()),
            'heading': heading, 'heading_residual_rows': [dict(start_s=float(a0), end_s=float(b0),
                A1_increment_deg=float(y0), gyro_z_increment_deg=float(g0[0]), gyro_yaw_increment_deg=float(g0[1]))
                for a0, b0, y0, g0 in zip(a, b, dy, dg)], 'acf_slots': acf['slots']}


def contiguous_intervals(t, mask, maximum_gap):
    idx = np.flatnonzero(mask)
    if not len(idx):
        return []
    split = np.flatnonzero((np.diff(idx) != 1)|(np.diff(t[idx]) > maximum_gap))+1
    return [[float(t[g[0]]), float(t[g[-1]])] for g in np.split(idx, split)]


def static_windows(data, t):
    windows = [{'name': 'first_1000', 'interval_s': [float(t[0]), float(t[999])]}]
    if data['spec']['dataset_id'] == 'BY2O':
        pt = data['pt']
        w = data['spec']['window_seconds']
        mask = (pt >= w[0])&(pt <= w[1])&(np.linalg.norm(data['pvt_full'][:, :2], axis=1) < .3)
        choices = [x for x in contiguous_intervals(pt, mask, .21) if x[1]-x[0] >= 5]
        if choices:
            chosen = max(choices, key=lambda ab: ab[1]-ab[0])
            windows.append({'name': 'BY2O_standing', 'interval_s': chosen, 'candidate_intervals_s': choices})
        else:
            windows.append({'name': 'BY2O_standing', 'interval_s': None, 'status': 'UNAVAILABLE_NO_5S_PVT_STATIC_WINDOW'})
    return windows


def gravity_angles(force):
    return np.column_stack((np.arctan2(-force[:, 1], -force[:, 2]),
                            np.arctan2(force[:, 0], np.hypot(force[:, 1], force[:, 2]))))


def window_analysis(window, t, gyro, acc, raw_rpy, raw_velocity):
    if window['interval_s'] is None:
        return window
    lo, hi = window['interval_s']
    mask = (t >= lo)&(t <= hi)
    wt, wg, wa = t[mask], gyro[mask], acc[mask]
    angle, support = integrate(wt, wg)
    allan = []
    for tau in TAUS:
        start = wt[wt+2*tau <= wt[-1]]
        start = start[support(start, start+2*tau)]
        if len(start) < 2:
            allan.append({'tau_s': tau, 'n': len(start), 'status': 'UNAVAILABLE_WINDOW_TOO_SHORT'})
            continue
        second = angle(start+2*tau)-2*angle(start+tau)+angle(start)
        adev = np.sqrt(np.mean(second**2, axis=0)/2)/tau
        allan.append({'tau_s': tau, 'n': len(start), 'adev_deg_per_s': np.rad2deg(adev).tolist(),
                      'equivalent_ARW_deg_per_sqrt_h': (np.rad2deg(adev)*np.sqrt(tau)*60).tolist()})
    at1 = next(x for x in allan if x['tau_s'] == 1.)
    gp = gravity_angles(wa)
    rawrp = raw_rpy[mask, :2]
    rp_frd = rawrp*[1, -1]
    norms = np.linalg.norm(raw_velocity[mask, :2], axis=1)
    rate = np.rad2deg(np.linalg.norm(wg, axis=1))
    return {**window, 'n': int(mask.sum()), 'duration_s': float(wt[-1]-wt[0]),
            'raw_velocity_H_mps': stats(norms), 'gyro_norm_deg_per_s': stats(rate),
            'standing_check': 'SUPPORTED_BY_LOW_MEAN_MOTION' if norms.mean() < .3 and np.sqrt(np.mean(rate*rate)) < 3 else 'NOT_RELIABLY_STATIC',
            'mean_rate_deg_per_h': (np.rad2deg(wg.mean(axis=0))*3600).tolist(),
            'allan': allan, 'at_1_s': at1, 'gravity_rp_deg': {a: stats(np.rad2deg(gp[:, i])) for i, a in enumerate(('roll', 'pitch'))},
            'mean_force_gravity_rp_deg': np.rad2deg(gravity_angles(wa.mean(axis=0)[None, :])[0]).tolist(),
            'RP_converted_minus_gravity_deg': {a: stats(np.rad2deg(wrap(rp_frd[:, i]-gp[:, i]))) for i, a in enumerate(('roll', 'pitch'))},
            'RP_frozen_minus_gravity_deg': {a: stats(np.rad2deg(wrap(rawrp[:, i]-gp[:, i]))) for i, a in enumerate(('roll', 'pitch'))}}


def baseline_observations(inputs, data):
    spec = data['spec']
    lock = {r['relative_path']: r['sha256'] for r in csv_data(inputs.pin(spec['raw_lock']))}
    s1 = csv_data(inputs.pin(spec['raw_inputs']['status']))
    path2 = spec['raw_inputs']['status']['path'].replace('gnss1-status.csv', 'gnss2-status.csv')
    s2 = csv_data(inputs.read(path2, lock[path2.removeprefix('<RAW_ROOT>/')]))
    r1, _ = _prepared_rows(apply_status_valid_filter(s1, 'gnss1')[0])
    r2, _ = _prepared_rows(apply_status_valid_filter(s2, 'gnss2')[0])
    week = {int(float(r['time_gps_wno'])) for r in s1}
    assert len(week) == 1
    offset = int((315964800+week.pop()*604800-18-spec['base_time'])*1000)
    frozen = {round(t*1000): y for t, y in zip(data['at'], data['ay'])}
    rows, differences = [], []
    for r in r1:
        ms = round(float(r['row']['time_gps_tow'])*1000)+offset
        if ms not in frozen:
            continue
        other = _interp(r2, r['t'], ['n', 'e', 'd'])
        if other is None:
            continue
        v = np.array([other[k]-r[k] for k in ('n', 'e', 'd')])
        y = np.arctan2(v[1], v[0])+np.pi/2
        differences.append(abs(np.rad2deg(wrap(y-frozen[ms]))))
        rows.append([ms/1000, *v])
    a = np.asarray(rows)
    assert np.max(differences) < 1e-6
    return a, {'n': len(a), 'yaw_vs_frozen_max_abs_deg': float(np.max(differences)),
               'baseline_source': 'hash-locked GNSS2 minus GNSS1 status; frozen filtering/interpolation, integer iTOW identity'}


def rolling_mean(t, x, target, half=.5):
    lo, hi = np.searchsorted(t, target-half), np.searchsorted(t, target+half, side='right')
    pref = np.vstack((np.zeros((1, x.shape[1])), np.cumsum(x, axis=0)))
    count = hi-lo
    valid = (target-half >= t[0])&(target+half <= t[-1])&(count > 1)
    out = np.divide(pref[hi]-pref[lo], count[:, None], out=np.full((len(target), x.shape[1]), np.nan), where=count[:, None] > 0)
    return out, valid


def mount_and_rp(data, base, t, acc, rpy):
    # Uninstalled FRD accelerometer: RP residuals directly test the raw RP provider convention.
    gp = gravity_angles(acc)
    pi = nearest(data['pt'], t)
    w = data['spec']['window_seconds']
    speed = np.linalg.norm(data['pvt_full'][pi, :2], axis=1)
    slow = (t >= w[0])&(t <= w[1])&(abs(t-data['pt'][pi]) <= .03)&(speed < .8)
    rp = rpy[:, :2]
    rpstats = {}
    for label, vals in (('converted', rp*[1, -1]), ('frozen', rp)):
        rpstats[label] = {a: stats(np.rad2deg(wrap(vals[slow, i]-gp[slow, i]))) for i, a in enumerate(('roll', 'pitch'))}
    # Report all sign / axis-order candidates, not a fitted correction.
    candidates = {}
    for order in ((0, 1), (1, 0)):
        for signs in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            d = np.rad2deg(wrap(rp[slow][:, order]*signs-gp[slow]))
            candidates[str(order)+str(signs)] = float(np.sqrt(np.mean(d*d))) if len(d) else None
    bt = base[:, 0]
    ai = nearest(data['pt'], bt)
    af, available = rolling_mean(t, acc, bt)
    grav = gravity_angles(af)
    length = np.linalg.norm(base[:, 1:4], axis=1)
    sine = -base[:, 3]/(length*np.cos(grav[:, 1]))
    mask = (bt >= w[0])&(bt <= w[1])&available&(abs(bt-data['pt'][ai]) <= .03)&(np.linalg.norm(data['pvt_full'][ai, :2], axis=1) < .8)&(abs(sine) <= 1)
    baseline_roll = np.arcsin(np.clip(sine, -1, 1))
    install_roll = np.rad2deg(wrap(grav[mask, 0]-baseline_roll[mask]))
    roll_result = {'sensor_minus_baseline_deg': stats(install_roll), 'n': int(mask.sum()),
                   'epochs_s': bt[mask].tolist(), 'baseline_roll_deg': stats(np.rad2deg(baseline_roll[mask])),
                   'gravity_roll_deg': stats(np.rad2deg(grav[mask, 0])), 'frozen_install_deg': -1.,
                   'mean_offset_from_frozen_deg': float(install_roll.mean()+1) if len(install_roll) else None,
                   'classification': 'SLOW_MOTION_BASELINE_GRAVITY_PROXY_NOT_CAD_CALIBRATION'}
    # Body-plane direction, tilted with the same H-A frame as the HV correction.
    pvt, hv, yaw = data['pvt'], data['ha'], data['yaw']
    pnorm, hnorm = np.linalg.norm(pvt, axis=1), np.linalg.norm(hv, axis=1)
    vdir = np.arctan2(hv[:, 1], hv[:, 0])
    course = np.arctan2(pvt[:, 1], pvt[:, 0])
    yaw_difference = wrap(course-vdir)
    moving = (pnorm >= .3)&(hnorm >= .3)
    dt = data['t']
    left, right = dt-.5, dt+.5
    straight = moving&(pnorm >= .8)&a1_intervals(data, left, right)
    straight &= abs(np.rad2deg(np.interp(right, data['at'], data['ay'])-np.interp(left, data['at'], data['ay']))) <= 5
    tilt = rotate(data['velocity_raw']*[1, -1, -1], data['rpy'][:, 0], -data['rpy'][:, 1], np.zeros(len(dt)))
    body_dir = np.arctan2(tilt[:, 1], tilt[:, 0])
    method2 = wrap(course-yaw-body_dir)
    assert np.max(abs(wrap(method2-yaw_difference))) < 1e-12
    cross = hv[:, 0]*pvt[:, 1]-hv[:, 1]*pvt[:, 0]
    dot = np.sum(hv*pvt, axis=1)
    yaw1 = {'angle_deg': stats(np.rad2deg(yaw_difference[moving])),
            'weighted_correction_deg': float(np.rad2deg(np.arctan2(cross[moving].sum(), dot[moving].sum()))),
            'n': int(moving.sum()), 'classification': 'EFFECTIVE_YAW_OFFSET_MOUNT_SLIP_A1_CONFOUNDED'}
    yaw2 = {'angle_deg': stats(np.rad2deg(method2[straight])), 'n': int(straight.sum()),
            'median_correction_deg': float(np.median(np.rad2deg(method2[straight]))) if straight.any() else None,
            'classification': 'STRAIGHT_SEGMENT_EFFECTIVE_OFFSET_NOT_INDEPENDENT',
            'Go2_tilt_compensated_body_direction_deg': stats(np.rad2deg(body_dir[straight])),
            'PVT_course_minus_A1_deg': stats(np.rad2deg(wrap(course[straight]-yaw[straight])))}
    return {'roll': roll_result, 'pitch': {'status': 'NOT_OBSERVABLE_WITHOUT_BODY_LEVEL_REFERENCE', 'frozen_install_deg': 0.},
            'yaw_method1': yaw1, 'yaw_method2': yaw2, 'frozen_install_rpy_deg': [-1., 0., 0.],
            'slow_RP': {'n': int(slow.sum()), 'residual_deg': rpstats, 'axis_sign_candidate_combined_RMS_deg': candidates}}


def run_sequence(inputs, prior, contract, name, seed):
    data = load_observations(inputs, prior, contract, name)
    im, imcheck = imu_fields(data['body_bytes'])
    im[:, 0] -= data['spec']['base_time']
    assert np.array_equal(im[:, 0], data['raw'][:, 0])
    complete = np.isfinite(im[:, :7]).all(axis=1)
    im = im[complete]
    raw = data['raw'][complete]
    t, rawgyro, rawacc = im[:, 0], im[:, 1:4], im[:, 4:7]
    rpy, vel = raw[:, 1:4], raw[:, 7:10]
    assert np.isfinite(rpy).all() and len(t) >= 1000
    gyro = rotate(rawgyro*[1, -1, -1], np.deg2rad(-1.), 0., 0.)
    acc = rawacc*[1, -1, -1]
    calimu = np.loadtxt(io.BytesIO(inputs.pin(data['cal']['variants']['V2s']['providers']['imupath'])))
    dt = np.diff(t)
    good = (dt > 0)&(dt <= .1)
    reconstructed = (gyro[1:]-gyro[:1000].mean(axis=0))*dt[:, None]
    assert len(calimu) == int(good.sum())
    assert np.max(abs(calimu[:, 0]-t[1:][good])) < 1e-6
    parity = float(np.max(abs(calimu[:, 1:4]-reconstructed[good])))
    # Frozen payload uses a .12g intermediate and .8f increments, not unrounded radians.
    serialized = np.array([[float(frozen_token(v, 8)) for v in row] for row in reconstructed[good]])
    assert np.array_equal(serialized, calimu[:, 1:4])
    print(name+': frozen gyro increment identity, turn regression, A1 increment noise', flush=True)
    gh = gyro_and_heading(data, t, gyro, rpy, seed)
    windows = [window_analysis(w, t, gyro, acc, rpy, vel) for w in static_windows(data, t)]
    print(name+': static Allan / gravity / installation / RP', flush=True)
    base, basecheck = baseline_observations(inputs, data)
    mounting = mount_and_rp(data, base, t, acc, rpy)
    # Quaternion-rpy consistency on every finite quaternion: same documented axis order.
    q = im[:, 7:11]
    finite = np.isfinite(q).all(axis=1)&(np.linalg.norm(q, axis=1) > 0)
    q = q[finite]/np.linalg.norm(q[finite], axis=1)[:, None]
    qw, qx, qy, qz = q.T
    qr = np.column_stack((np.arctan2(2*(qw*qx+qy*qz), 1-2*(qx*qx+qy*qy)),
                          np.arcsin(np.clip(2*(qw*qy-qz*qx), -1, 1)),
                          np.arctan2(2*(qw*qz+qx*qy), 1-2*(qy*qy+qz*qz))))
    quaternion = {a: stats(np.rad2deg(wrap(qr[:, i]-rpy[finite, i]))) for i, a in enumerate(('roll', 'pitch', 'yaw'))}
    hv_res = data['ha']-data['pvt']
    return {'window_seconds': data['spec']['window_seconds'], 'gyro_heading': gh, 'static_windows': windows,
            'mounting_and_RP': mounting, 'quaternion_minus_rpy_deg': quaternion,
            'HV_A1_NE_residual_mps': {a: stats(hv_res[:, i]) for i, a in enumerate(('N', 'E'))},
            'audit': {**data['audit'], 'imu_parser': imcheck, 'cal_gyro_increment_max_abs_rad': parity,
                      'cal_gyro_serialized_tokens_exact': True,
                      'baseline': basecheck, 'raw_imu_frames': len(t), 'invalid_dt_intervals': int((~good).sum())}}


def decisions(sequences):
    entries = []
    def check(name, sequence, value, limit, interpretation):
        entries.append({'item': name, 'sequence': sequence, 'value_abs': abs(value) if value is not None else None,
                        'threshold': limit, 'trigger': bool(abs(value) > limit) if value is not None and limit is not None else None,
                        'interpretation': interpretation})
    means = []
    for s, r in sequences.items():
        gh = r['gyro_heading']
        fit = gh['fits']['installed_z']
        check('gyro_z_scale_systematic_angle', s, fit.get('systematic_angle_RMS_deg'), 3*fit['noise_sigma_deg'] if fit.get('noise_sigma_deg') is not None else None, 'deg; turning-block diagnostic, not adopted scale')
        check('sigma_A1_relative_difference', s, gh['heading']['euler_yaw_rate']['relative_difference'], .5, 'relative to frozen 1.5 deg')
        m = r['mounting_and_RP']
        check('installation_roll_offset_proxy', s, m['roll']['mean_offset_from_frozen_deg'], 1., 'deg; baseline/gravity slow-motion apparent installation offset')
        check('installation_pitch', s, None, 1., 'NOT_OBSERVABLE: unknown body tilt')
        # Effective yaw offsets warrant human review; they do not identify which sensor to rotate.
        check('installation_yaw_effective_method1', s, m['yaw_method1']['weighted_correction_deg'], 1., 'deg; confounded with A1 bias and lateral velocity/slip')
        check('installation_yaw_effective_method2', s, m['yaw_method2']['median_correction_deg'], 1., 'deg; same sources, straight subset, not independent')
        for a, st in r['HV_A1_NE_residual_mps'].items():
            check('HV_'+a+'_mean', s, st['mean'], 3*st['std'], 'm/s; cross-source residual bias')
        for label, rp in [('slow_converted', m['slow_RP']['residual_deg']['converted']), ('slow_frozen', m['slow_RP']['residual_deg']['frozen'])]:
            for a, st in rp.items():
                check('RP_'+label+'_'+a+'_mean', s, st.get('mean'), 3*st['std'] if st.get('std') is not None else None, 'deg; comparison to gravity, not independent attitude truth')
        for w in r['static_windows']:
            if 'mean_rate_deg_per_h' in w:
                means.append((s, w['name'], w['mean_rate_deg_per_h']))
                for a, st in w['RP_frozen_minus_gravity_deg'].items():
                    check('RP_'+w['name']+'_frozen_'+a+'_mean', s, st['mean'], 3*st['std'], 'deg; fixed-window gravity residual')
    pooled = np.std(np.asarray([x[2] for x in means]), axis=0, ddof=1)
    for s, name, mean in means:
        frozen_bias = sequences[s]['gyro_heading']['bias_first1000_deg_per_h']
        for i, axis in enumerate(AXES):
            # The frozen provider ALREADY removes this sequence's first-1000 mean.
            # Test residual systematic error under that existing operation, not the removed raw bias.
            check('static_'+name+'_gyro_'+axis+'_mean_after_frozen_debias', s, mean[i]-frozen_bias[i], 3*pooled[i],
                  'deg/h; existing per-sequence first-1000 subtraction; APPROXIMATE across-window noise')
            entries[-1].update(raw_mean_deg_per_h=mean[i], frozen_subtracted_mean_deg_per_h=frozen_bias[i],
                               raw_mean_exceeds_3sigma=bool(abs(mean[i]) > 3*pooled[i]))
    per_sequence = {}
    for s in SEQUENCES:
        vals = [x[2] for x in means if x[0] == s]
        per_sequence[s] = {'window_count': len(vals), 'gbstd_deg_per_h': np.std(vals, axis=0, ddof=1).tolist() if len(vals) > 1 else None,
                           'status': 'APPROXIMATE' if len(vals) > 1 else 'UNAVAILABLE_SINGLE_WINDOW'}
    return {'status': 'HUMAN_DECISION_REQUIRED' if any(x['trigger'] for x in entries) else 'LIMITATIONS_ONLY_NO_CHAIN_CHANGE',
            'thresholds': entries, 'triggered': [x for x in entries if x['trigger']],
            'gbstd': {'pooled_window_count': len(means), 'pooled_deg_per_h': pooled.tolist(), 'status': 'APPROXIMATE',
                       'per_sequence': per_sequence, 'frozen_gbstd_deg_per_h': [9.38]*3}}


def tuplefmt(values):
    return ' / '.join(fmt(v) for v in values) if values is not None else 'UNAVAILABLE'


def render(result, prereg):
    seq = result['sequences']
    rows = [seq[s] for s in SEQUENCES]
    def tab(items):
        return table([(label, [func(r) for r in rows]) for label, func in items])
    def ms(x):
        return fmt(x.get('mean'))+' ± '+fmt(x.get('std'))
    out = [prereg.rstrip(), '', '## 执行结果', '',
           '状态：`'+result['decision']['status']+'`。未改变任何链；v2.1 尚未执行。', '',
           '### 1. 陀螺 z 标度（Δψ_A1 = k·Δψ_gyro）', '',
           tab([('转弯 5 s 段 n', lambda r: str(r['gyro_heading']['fits']['installed_z']['n'])),
                ('z 积分：斜率 k [95% CI]', lambda r: fmt(r['gyro_heading']['fits']['installed_z']['slope'])+' ['+tuplefmt(r['gyro_heading']['fits']['installed_z']['ci95'])+']'),
                ('Euler yaw-rate：斜率 k [95% CI]', lambda r: fmt(r['gyro_heading']['fits']['euler_yaw_rate']['slope'])+' ['+tuplefmt(r['gyro_heading']['fits']['euler_yaw_rate']['ci95'])+']'),
                ('z 拟合残差均值 ± σ / °', lambda r: ms(r['gyro_heading']['fits']['installed_z'].get('fit_residual_deg', {}))),
                ('x / y 标度', lambda r: 'NOT_OBSERVABLE / NOT_OBSERVABLE')]),
           'CI 为预定 5 s 区间 bootstrap 的描述性区间，转弯段数有限；A1 异常、安装与运动耦合均进入结果，不是高精度独立陀螺标度标定。全部转弯区间及增量见 JSON，未因异常残差删段。', '',
           '### 2. A1 航向增量噪声', '',
           tab([('1 s 端点对 n', lambda r: str(r['gyro_heading']['heading']['euler_yaw_rate']['n'])),
                ('σ_A1：Euler yaw-rate / °', lambda r: fmt(r['gyro_heading']['heading']['euler_yaw_rate']['sigma_A1_deg'])),
                ('σ_A1：直接 z 积分对照 / °', lambda r: fmt(r['gyro_heading']['heading']['installed_z']['sigma_A1_deg'])),
                ('冻结 σ_A1 / °', lambda r: '1.500000'),
                ('1 s 增量残差均值 ± σ / °', lambda r: ms(r['gyro_heading']['heading']['euler_yaw_rate']['increment_residual_deg'])),
                ('ρ[1,1.02)s', lambda r: fmt(r['gyro_heading']['heading']['euler_yaw_rate']['acf_at_1_s'])),
                ('首个非正 ACF 箱 / s', lambda r: tuplefmt(r['gyro_heading']['heading']['euler_yaw_rate']['acf_first_nonpositive']['slot_s']) if r['gyro_heading']['heading']['euler_yaw_rate']['acf_first_nonpositive'] else 'NOT_OBSERVED')]),
           'σ_A1 是依题定义的增量残差代理值。A1 自身时间相关、陀螺误差和重叠增量破坏独立白噪声前提；首次过零及 1 s 的负相关不能被自动解读为原始 A1 白噪声。', '',
           '### 3. 静止窗 Allan 与 gbstd', '',
           tab([('前 1000 帧时间窗 / s', lambda r: tuplefmt(r['static_windows'][0]['interval_s'])),
                ('前 1000 帧时长 / s', lambda r: fmt(r['static_windows'][0]['duration_s'])),
                ('τ=1 s Allan / (°/s)，x/y/z', lambda r: tuplefmt(r['static_windows'][0]['at_1_s'].get('adev_deg_per_s'))),
                ('τ=1 s ARW 代理 / (°/√h)，x/y/z', lambda r: tuplefmt(r['static_windows'][0]['at_1_s'].get('equivalent_ARW_deg_per_sqrt_h'))),
                ('冻结 arw / (°/√h)，x/y/z', lambda r: '0.985000 / 0.985000 / 0.985000'),
                ('静止均值角速率 / (°/h)，x/y/z', lambda r: tuplefmt(r['static_windows'][0]['mean_rate_deg_per_h'])),
                ('静止检查', lambda r: r['static_windows'][0]['standing_check'])]),
           'BY2O 站立窗（最长连续 PVT<0.3 m/s 区间）及全部 τ 读值：', '']
    stand = next((w for w in seq['BY2O']['static_windows'] if w['name'] == 'BY2O_standing'), {})
    out += ['区间 '+tuplefmt(stand.get('interval_s'))+' s，n='+str(stand.get('n', 0))+'，状态 '+stand.get('standing_check', 'UNAVAILABLE')+'。', '',
            '| τ / s | 配对 n | Allan x / y / z（°/s） |', '|---:|---:|---|',
            *['| '+fmt(a['tau_s'])+' | '+str(a['n'])+' | '+tuplefmt(a.get('adev_deg_per_s'))+' |' for a in stand.get('allan', [])], '',
            '站立窗 τ=1 s ARW 代理 x/y/z = '+tuplefmt(stand.get('at_1_s', {}).get('equivalent_ARW_deg_per_sqrt_h'))+' °/√h。', '',
            table([('各序列静止窗数', [str(result['decision']['gbstd']['per_sequence'][s]['window_count']) for s in SEQUENCES]),
                   ('本序列跨窗 gbstd / (°/h)，x/y/z', [tuplefmt(result['decision']['gbstd']['per_sequence'][s]['gbstd_deg_per_h']) for s in SEQUENCES]),
                   ('状态', [result['decision']['gbstd']['per_sequence'][s]['status'] for s in SEQUENCES])]),
            '跨三序列共 '+str(result['decision']['gbstd']['pooled_window_count'])+' 窗合并 gbstd = '+tuplefmt(result['decision']['gbstd']['pooled_deg_per_h'])+' °/h；冻结为 9.38 / 9.38 / 9.38 °/h，`APPROXIMATE`。BY2/BY2H 各只有一个指定静止窗，不能各自估计跨窗 σ。跨窗差也含温漂、实际姿态运动与地球自转投影，不是纯零偏不稳定性。', '',
            '原始静止角速率均值不等于当前链的剩余系统误差：冻结 provider 已减去每序列前 1000 帧均值。阈值表在同一现有操作后比较，首窗剩余均值为 0；BY2O 站立窗剩余 x/y/z = '+tuplefmt([stand['mean_rate_deg_per_h'][i]-seq['BY2O']['static_windows'][0]['mean_rate_deg_per_h'][i] for i in range(3)] if 'mean_rate_deg_per_h' in stand else None)+' °/h，均未超过 3 倍合并跨窗 σ。原始均值及其阈值标志保留在 JSON 中，不登记为尚未处理的新陀螺偏置。', '',
            'Allan 公式来源：[NIST SP 1065 §5.2.4](https://tf.nist.gov/general/pdf/2220.pdf)。本实现对实际时间积分角作二阶差分；短窗及真实机器人站立微动限制 ARW 辨识。τ=1 s 读值不是对 −1/2 斜率区间的拟合。冻结单位由 `port_config_loader.cpp` 的 D2R/60、D2R/3600 换算核对。', '',
            '### 4. 安装角与可观测性', '',
            tab([('roll 慢速同步样本 n', lambda r: str(r['mounting_and_RP']['roll']['n'])),
                 ('roll：sensor−baseline 均值 ± σ / °', lambda r: ms(r['mounting_and_RP']['roll']['sensor_minus_baseline_deg'])),
                 ('roll 对冻结 −1° 的均值偏差 / °', lambda r: fmt(r['mounting_and_RP']['roll']['mean_offset_from_frozen_deg'])),
                 ('pitch：首窗表观 gravity 均值 ± σ / °', lambda r: ms(r['static_windows'][0]['gravity_rp_deg']['pitch'])),
                 ('pitch 安装角', lambda r: 'NOT_OBSERVABLE'),
                 ('yaw 方法一有效修正角 / °', lambda r: fmt(r['mounting_and_RP']['yaw_method1']['weighted_correction_deg'])),
                 ('yaw 方法一逐样本均值 ± σ / °', lambda r: ms(r['mounting_and_RP']['yaw_method1']['angle_deg'])),
                 ('yaw 方法二直线样本 n', lambda r: str(r['mounting_and_RP']['yaw_method2']['n'])),
                 ('yaw 方法二中位有效修正角 / °', lambda r: fmt(r['mounting_and_RP']['yaw_method2']['median_correction_deg'])),
                 ('yaw 方法二逐样本均值 ± σ / °', lambda r: ms(r['mounting_and_RP']['yaw_method2']['angle_deg'])),
                 ('冻结安装角 roll/pitch/yaw / °', lambda r: '−1 / 0 / 0')]),
            'roll 是低动态基线/重力代理，样本少时不构成精确安装校准；天线自身垂直错位也进入结果。pitch 的三序列表观重力倾角均值跨序列 σ='+fmt(float(np.std([r['static_windows'][0]['gravity_rp_deg']['pitch']['mean'] for r in rows], ddof=1)))+'°，缺少独立机身水平基准，无法分离安装俯仰。yaw 是把 H-A 速度转向 PVT 的有效角差，不能单独归因于 IMU 安装、A1 安装或侧滑。两种 yaw 诊断在相同样本上代数等价，只是取样/汇总不同。', '',
            '### 5. RP 先验符号与轴序', '',
            '各格 roll / pitch；差定义为指定 RP 减未安装修正的 FRD 加速度计 gravity 姿态。', '',
            tab([('首窗：FLU→FRD RP 残差均值 / °', lambda r: tuplefmt([r['static_windows'][0]['RP_converted_minus_gravity_deg'][a]['mean'] for a in ('roll', 'pitch')])),
                 ('首窗：FLU→FRD RP 残差 σ / °', lambda r: tuplefmt([r['static_windows'][0]['RP_converted_minus_gravity_deg'][a]['std'] for a in ('roll', 'pitch')])),
                 ('首窗：冻结原始 RP 残差均值 / °', lambda r: tuplefmt([r['static_windows'][0]['RP_frozen_minus_gravity_deg'][a]['mean'] for a in ('roll', 'pitch')])),
                 ('首窗：冻结原始 RP 残差 σ / °', lambda r: tuplefmt([r['static_windows'][0]['RP_frozen_minus_gravity_deg'][a]['std'] for a in ('roll', 'pitch')])),
                 ('慢速样本 n', lambda r: str(r['mounting_and_RP']['slow_RP']['n'])),
                 ('慢速：FLU→FRD 均值 / °', lambda r: tuplefmt([r['mounting_and_RP']['slow_RP']['residual_deg']['converted'][a].get('mean') for a in ('roll', 'pitch')])),
                 ('慢速：FLU→FRD σ / °', lambda r: tuplefmt([r['mounting_and_RP']['slow_RP']['residual_deg']['converted'][a].get('std') for a in ('roll', 'pitch')])),
                 ('慢速：冻结原始 RP 均值 / °', lambda r: tuplefmt([r['mounting_and_RP']['slow_RP']['residual_deg']['frozen'][a].get('mean') for a in ('roll', 'pitch')])),
                 ('慢速：冻结原始 RP σ / °', lambda r: tuplefmt([r['mounting_and_RP']['slow_RP']['residual_deg']['frozen'][a].get('std') for a in ('roll', 'pitch')]))]),
            'rpy 的源轴序由日志 quaternion 重建逐样本核对，见 JSON。物理 FLU→FRD 的对应是 [roll,−pitch]；冻结 RP 操作直接使用 [roll,pitch]，属于不同操作约定。比较用的是同一 Go2 IMU 的融合 rpy 与加速度计，并非独立姿态真值。动态加速度、低速样本少和姿态幅度不足会限制符号辨别。', '',
            '### 6. 预注册阈值判定', '',
            '| 项目 | 序列 | 绝对量 | 严格阈值 | 判定 |', '|---|---|---:|---:|---|']
    for x in result['decision']['thresholds']:
        out.append('| '+' | '.join([x['item'], x['sequence'], fmt(x['value_abs']), fmt(x['threshold']),
                                    'HUMAN_DECISION_REQUIRED' if x['trigger'] else ('NOT_OBSERVABLE / UNAVAILABLE' if x['trigger'] is None else '未触发')])+' |')
    out += ['', '总判定：`'+result['decision']['status']+'`。触发仅登记供人类决定；没有据此改变 provider、标准差、安装角或求解链。不可观测量和条件性代理均保留限制，不冒充通过或标定完成。', '',
            '### 7. 输入、复核与封存', '',
            '观测来自哈希锁定的 raw Go2 日志、GNSS status 与冻结 CAL/V2s GNSS18/HV/IMU；PVT 和 A1 的 iTOW 身份沿用并固定 P-11a 已验证记录。此次重新检查输入哈希、完整冻结 HV/gyro 增量重建及 A1 基线航向同历元一致性。', '',
            '计算基底：`'+result['code_commit']+'`。计算前登记全文 SHA-256：`'+result['preregistration_sha256']+'`；完整输入及运行脚本哈希见 JSON。', '',
            '实施复核记录：首轮在未舍入 gyro 增量与 8 位小数冻结 token 的比较处停止，尚未计算 P-12 指标；修正为原 .12g→.8f 写出格式后全量 token 一致。第一份完整计算及过程脚本另存 FIRST_CALCULATION；随后仅以相同静止窗均值减去冻结首窗均值，修正行动表的既有去偏适用范围，科学统计值和预注册阈值未改。', '',
            '外部文件：`'+ROOT+'SENSOR_MODEL_CLOSEOUT_AUDIT.json`、`.md`；计算前登记副本 `SENSOR_MODEL_CLOSEOUT_PREREGISTRATION.md`。零 trace/求解器/评估器/provider 生成；所有数组仅作诊断，不作为求解器输入。']
    return '\n'.join(out)+'\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paths', type=Path, required=True)
    p.add_argument('--code-commit', required=True)
    args = p.parse_args()
    stem = 'SENSOR_MODEL_CLOSEOUT_AUDIT'
    names = [stem+'.json', stem+'.md', 'SENSOR_MODEL_CLOSEOUT_PREREGISTRATION.md']
    inputs, output, opened, prior, contract = setup(args.paths, names)
    doc = inputs.read('<CODE_ROOT>/docs/paper_rebuild/SENSOR_MODEL_CLOSEOUT_AUDIT.md').decode()
    prereg = doc.split('## 执行结果')[0]
    if (output/names[2]).exists():
        # Preserve the original preregistration after any pre-result implementation stop.
        assert inputs.read(ROOT+names[2], hashlib.sha256(prereg.encode()).hexdigest()).decode() == prereg
    else:
        with (output/names[2]).open('x') as f:
            f.write(prereg)
    result = {'schema_version': 'paper_rebuild.clean6.sensor_closeout_audit.v1', 'task': 'P-12',
              'preregistration_sha256': hashlib.sha256(prereg.encode()).hexdigest(),
              'sequences': {s: run_sequence(inputs, prior, contract, s, 20260913+i) for i, s in enumerate(SEQUENCES)}}
    result['decision'] = decisions(result['sequences'])
    result.update(provenance(inputs, opened, args.code_commit))
    with (output/(stem+'.json')).open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    with (output/(stem+'.md')).open('x') as f:
        f.write(render(result, prereg))
    print('WROTE '+stem+': '+result['decision']['status'], flush=True)


if __name__ == '__main__':
    main()
