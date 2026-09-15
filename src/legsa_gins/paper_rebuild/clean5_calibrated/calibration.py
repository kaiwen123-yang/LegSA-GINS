"""P06 preregistered residual-variance calibration, with no reference input.

The input dvel is already the frozen V2s increment: scale, measured dt,
FLU-to-FRD and installation rotation have each been applied exactly once.
This module only rotates that increment from body FRD into NED.
"""
from __future__ import annotations

import math
import numpy as np

AXES = ('north', 'east', 'down')
LAGS_MS = (200, 400, 600, 800, 1000, 1500, 2000)


def timeline(values, name):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all() or np.any(np.diff(x) <= 0):
        raise ValueError(name + ': expected finite strictly increasing timeline')
    return x


def matrix(values, count, columns, name):
    x = np.asarray(values, dtype=float)
    if x.shape != (count, columns) or not np.isfinite(x).all():
        raise ValueError(name + ': shape or finite-value failure')
    return x


def body_to_ned(roll, pitch, yaw):
    """Rz(yaw) Ry(pitch) Rx(roll), matching the frozen FRD/NED convention."""
    roll, pitch, yaw = np.broadcast_arrays(roll, pitch, yaw)
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    return np.stack((cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr,
                     sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr,
                     -sp, cp*sr, cp*cr), axis=-1).reshape(roll.shape+(3, 3))


def attitude_at(times, rpy_times, roll_pitch, a1_times, yaw, max_gap_s=1.2):
    """Linear roll/pitch and unwrapped linear A1 yaw, without extrapolation."""
    t = np.asarray(times, float)
    rt = timeline(rpy_times, 'Go2 rpy time')
    at = timeline(a1_times, 'A1 time')
    rp = matrix(roll_pitch, len(rt), 2, 'Go2 roll/pitch')
    y = np.asarray(yaw, float)
    if y.shape != at.shape or not np.isfinite(y).all():
        raise ValueError('A1 yaw shape/finite failure')
    support = (t >= rt[0]) & (t <= rt[-1]) & (t >= at[0]) & (t <= at[-1])
    j = np.clip(np.searchsorted(at, t, side='right')-1, 0, len(at)-2)
    # Endpoints retain their own observed heading; only the open gap is skipped.
    in_gap = (at[j+1]-at[j] > max_gap_s) & (t > at[j]) & (t < at[j+1])
    support &= ~in_gap
    r = np.interp(t, rt, rp[:, 0])
    p = np.interp(t, rt, rp[:, 1])
    y = np.interp(t, at, np.unwrap(y))
    return body_to_ned(r, p, y), support


def fit_axis(lag_seconds, variances, window_means, frozen_vrw, frozen_abstd):
    """Unweighted OLS with intercept, ddof=1 window spread, preregistered fallback."""
    x, y = np.asarray(lag_seconds, float), np.asarray(variances, float)
    if x.shape != y.shape or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('OLS data invalid')
    means = np.asarray(window_means, float)
    if not np.isfinite(means).all():
        raise ValueError('Window means nonfinite')
    q = c = None
    if len(x) >= 2 and np.ptp(x) > 0:
        q, c = (float(z) for z in np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), y, rcond=None)[0])
    reasons = []
    if q is None:
        reasons.append('UNAVAILABLE_OLS_SLOPE')
    elif q <= 0:
        reasons.append('NONPOSITIVE_Q')
    if len(means) < 3:
        reasons.append('FEWER_THAN_THREE_NONEMPTY_WINDOWS')
    spread = float(np.std(means, ddof=1)) if len(means) >= 2 else None
    return {'status': 'FALLBACK' if reasons else 'CALIBRATED', 'fallback_reasons': reasons,
            'q_m2ps3': q, 'c_m2ps2': c, 'ols_lag_count': len(x),
            'nonempty_window_count': len(means), 'window_mean_acceleration_std_mps2': spread,
            'estimated_vrw_mps_sqrt_hour': math.sqrt(q)*60 if q is not None and q > 0 else None,
            'estimated_abstd_mGal': spread*1e5 if spread is not None else None,
            'vrw_mps_sqrt_hour': float(frozen_vrw) if reasons else math.sqrt(q)*60,
            'abstd_mGal': float(frozen_abstd) if reasons else spread*1e5}


def calibrate_arrays(*, imu_times_s, imu_dvel_mps, imu_dt_s, rpy_times_s,
                     roll_pitch_rad, a1_times_s, yaw_rad, pvt_itow_ms,
                     pvt_times_s, pvt_velocity_mps, window, g_local_mps2,
                     frozen_vrw=(.077, .077, .077), frozen_abstd=(77.8, 77.8, 77.8),
                     lags_ms=LAGS_MS, max_heading_gap_s=1.2, bias_window_s=60.):
    """Return a model summary and complete residual/variance/window ledgers.

    PVT epochs are matched by exact integer iTOW. Pairs lacking continuous A1
    support are unavailable. Existing IMU input gaps are neither filled nor
    residual-filtered; their measured-dt coverage is recorded for every pair.
    """
    it = timeline(imu_times_s, 'IMU time')
    dv = matrix(imu_dvel_mps, len(it), 3, 'V2s dvel')
    dt = np.asarray(imu_dt_s, float)
    if dt.shape != it.shape or not np.isfinite(dt).all() or np.any((dt <= 0) | (dt > .1)):
        raise ValueError('IMU measured dt must retain frozen valid intervals (0,.1]')
    pt = timeline(pvt_times_s, 'PVT time')
    pk = np.asarray(pvt_itow_ms)
    if pk.shape != pt.shape or not np.issubdtype(pk.dtype, np.integer) or np.any(np.diff(pk) <= 0):
        raise ValueError('PVT identity must be strictly increasing integer milliseconds')
    if not np.allclose(np.diff(pt), np.diff(pk)/1000., rtol=0, atol=5e-7):
        raise ValueError('PVT iTOW/time mapping inconsistent')
    pv = matrix(pvt_velocity_mps, len(pt), 3, 'PVT velocity NED')
    start, end = map(float, window)
    if not start < end or not math.isfinite(g_local_mps2) or g_local_mps2 <= 0:
        raise ValueError('Invalid calibration window/gravity')
    rotation, support = attitude_at(it, rpy_times_s, roll_pitch_rad, a1_times_s, yaw_rad, max_heading_gap_s)
    rotated = np.einsum('nij,nj->ni', rotation, dv)
    cumulative = np.vstack((np.zeros(3), np.cumsum(rotated, axis=0)))
    bad = np.r_[0, np.cumsum(~support)]
    coverage = np.r_[0., np.cumsum(dt)]
    at = np.asarray(a1_times_s, float)
    gaps = [(float(a), float(b)) for a, b in zip(at[:-1], at[1:]) if b-a > max_heading_gap_s]
    pindex = {int(k): i for i, k in enumerate(pk)}
    residual_rows, variance_rows, accepted = [], [], {}
    for lag_ms in lags_ms:
        if not isinstance(lag_ms, (int, np.integer)) or lag_ms <= 0:
            raise ValueError('Lag must be positive integer milliseconds')
        lag = lag_ms/1000.
        rows = []
        for i, key in enumerate(pk):
            j = pindex.get(int(key)+int(lag_ms))
            if j is None or not (start <= pt[i] and pt[j] <= end):
                continue
            t, te = float(pt[i]), float(pt[j])
            lo, hi = np.searchsorted(it, (t, te), side='right')
            endpoints_supported = (rpy_times_s[0] <= t <= te <= rpy_times_s[-1]
                                   and at[0] <= t <= te <= at[-1])
            gap_crossing = any(t < b and te > a for a, b in gaps)
            valid = hi > lo and endpoints_supported and not gap_crossing and bad[hi] == bad[lo]
            row = {'lag_ms': int(lag_ms), 'lag_s': lag, 'start_itow_ms': int(key),
                   'end_itow_ms': int(pk[j]), 'start_time_s': t, 'end_time_s': te,
                   'imu_sample_count': int(hi-lo), 'imu_dt_covered_s': float(coverage[hi]-coverage[lo]),
                   'imu_dt_coverage_minus_lag_s': float(coverage[hi]-coverage[lo]-lag),
                   'status': 'ACCEPTED' if valid else 'UNAVAILABLE_ATTITUDE_OR_IMU_SUPPORT'}
            if valid:
                delta_imu = cumulative[hi]-cumulative[lo]+np.array([0., 0., g_local_mps2*lag])
                delta_gnss = pv[j]-pv[i]
                residual = delta_imu-delta_gnss
                for axis, name in enumerate(AXES):
                    row['delta_v_imu_'+name+'_mps'] = float(delta_imu[axis])
                    row['delta_v_pvt_'+name+'_mps'] = float(delta_gnss[axis])
                    row['residual_'+name+'_mps'] = float(residual[axis])
                rows.append(row)
            residual_rows.append(row)
        accepted[int(lag_ms)] = rows
        for axis in AXES:
            vals = [r['residual_'+axis+'_mps'] for r in rows]
            variance_rows.append({'axis': axis, 'lag_ms': int(lag_ms), 'lag_s': lag,
                                  'exact_pair_count': sum(r['lag_ms'] == lag_ms for r in residual_rows),
                                  'sample_count': len(vals), 'ddof': 1,
                                  'variance_m2ps2': float(np.var(vals, ddof=1)) if len(vals) >= 2 else None,
                                  'mean_residual_mps': float(np.mean(vals)) if vals else None,
                                  'status': 'AVAILABLE' if len(vals) >= 2 else 'UNAVAILABLE'})
    complete_windows = int(math.floor((end-start)/bias_window_s))
    window_rows = []
    for w in range(complete_windows):
        left, right = start+w*bias_window_s, start+(w+1)*bias_window_s
        pairs = [r for r in accepted.get(1000, []) if left <= r['start_time_s'] and r['end_time_s'] <= right]
        for axis in AXES:
            values = [r['residual_'+axis+'_mps']/1. for r in pairs]
            window_rows.append({'axis': axis, 'window_index': w, 'window_start_s': left,
                                'window_end_s': right, 'sample_count': len(values),
                                'mean_residual_acceleration_mps2': float(np.mean(values)) if values else None,
                                'status': 'AVAILABLE' if values else 'UNAVAILABLE'})
    axes = {}
    for index, axis in enumerate(AXES):
        vals = [r for r in variance_rows if r['axis'] == axis and r['status'] == 'AVAILABLE']
        means = [r['mean_residual_acceleration_mps2'] for r in window_rows if r['axis'] == axis and r['status'] == 'AVAILABLE']
        axes[axis] = fit_axis([r['lag_s'] for r in vals], [r['variance_m2ps2'] for r in vals], means,
                              frozen_vrw[index], frozen_abstd[index])
    fallback = sum(a['status'] == 'FALLBACK' for a in axes.values())
    summary = {'status': 'STOP_ALL_AXES_FALLBACK' if fallback == 3 else 'CALIBRATION_COMPLETE',
               'axis_order': list(AXES), 'axes': axes, 'fallback_axis_count': fallback,
               'vrw': [axes[a]['vrw_mps_sqrt_hour'] for a in AXES],
               'abstd': [axes[a]['abstd_mGal'] for a in AXES],
               'window_s': [start, end], 'g_local_mps2': float(g_local_mps2),
               'complete_bias_window_count': complete_windows,
               'unused_partial_bias_window_s': [start+complete_windows*bias_window_s, end],
               'a1_gap_intervals_s': [list(x) for x in gaps],
               'rotation': 'Rz(A1 NED yaw) Ry(raw Go2 pitch) Rx(raw Go2 roll)',
               'increment_convention': 'V2s already scaled; frozen current-sample measured-dt increments; no second dt/scale/install',
               'coriolis_included': False, 'gnss_velocity_interpolation': False,
               'residual_clipping': False, 'missing_imu_interval_filling': False,
               'ned_axis_values_written_without_rotation_fitting': True,
               'residual_count': sum(r['status'] == 'ACCEPTED' for r in residual_rows),
               'unavailable_pair_count': sum(r['status'] != 'ACCEPTED' for r in residual_rows)}
    return summary, residual_rows, variance_rows, window_rows
