"""Pure D3 calibration: installed gyro-z primary, Euler and 0.2 s report only."""
from __future__ import annotations

from collections import Counter
import math
import numpy as np

from .t5a_diagnostics import _array, _imu_diagnostics, _interval_supported, _rp_at
from .t5a_provider import carr_soln
from .t5bc_provider import _key, _number, _mapping

BASELINE_M = .35
PAIR_POLICY = 'PAIR_ENDPOINTS_WITH_MULTIPLICITY'


def _sources(raw_yaw_rows, pacc1_m, pacc2_m, pvt_flags1, pvt_flags2, window):
    if len(window) != 2 or any(_number(x) is None for x in window) or window[1] <= window[0]:
        raise ValueError('A finite ordered closed window is required')
    pa1, pa2, fl1, fl2 = map(_mapping, (pacc1_m, pacc2_m, pvt_flags1, pvt_flags2))
    source = {}
    for row in raw_yaw_rows:
        key = _key(row['itow_ms'])
        yaw, timestamp = _number(row.get('yaw_ned_deg')), _number(row.get('aligned_time'))
        if key in source or yaw is None or timestamp is None:
            raise ValueError('Raw heading/time must be finite and epochs unique')
        flags = [carr_soln(m[key]) if key in m else None for m in (fl1, fl2)]
        pacc = [_number(m.get(key)) for m in (pa1, pa2)]
        s = sum(x*x for x in pacc) if all(x is not None and x >= 0 for x in pacc) else None
        if s is not None and not math.isfinite(s):
            raise ValueError('Nonfinite endpoint pAcc squared sum')
        vector = [_number(row.get(k)) for k in ('rel_n', 'rel_e', 'rel_d')]
        source[key] = dict(time=timestamp, yaw_rad=math.radians(yaw), fixed=flags == [2, 2],
                           S=s, vector=vector if None not in vector else None)
    ordered = sorted(source)
    if not ordered:
        raise ValueError('Empty raw heading input')
    for a, b in zip(ordered, ordered[1:]):
        if source[b]['time'] <= source[a]['time']:
            raise ValueError('Raw iTOW and relative time order disagree')
        if abs(source[b]['time']-source[a]['time']-(b-a)*.001) > 1e-6:
            raise ValueError('Raw relative timestamps disagree with exact iTOW differences')
    blocks, block = [], []
    for key in ordered:
        if not source[key]['fixed'] or block and key-block[-1] != 200:
            if block: blocks.append(block)
            block = []
        if source[key]['fixed']: block.append(key)
    if block: blocks.append(block)
    for keys in blocks:
        for key, value in zip(keys, np.unwrap([source[k]['yaw_rad'] for k in keys])):
            source[key]['unwrapped_yaw_rad'] = float(value)
    return source, ordered


def _pairs(source, ordered, lag, window):
    for key in ordered:
        first, second = source[key], source.get(key+lag)
        if not window[0] <= first['time'] <= window[1] or first['time']+lag*.001 > window[1]+1e-9:
            continue
        row = dict(lag_ms=lag, first_itow_ms=key, second_itow_ms=key+lag,
                   first_time_s=first['time'], second_time_s=second['time'] if second else None,
                   status='UNAVAILABLE', reason=None)
        interval = [source.get(k) for k in range(key, key+lag+1, 200)]
        if any(item is None for item in interval): row['reason'] = 'MISSING_EXACT_200MS_RAW_EPOCH'
        elif any(not item['fixed'] for item in interval): row['reason'] = 'INTERVAL_NOT_BOTH_FIXED'
        elif first['S'] is None or second['S'] is None: row['reason'] = 'ENDPOINT_PACC_UNAVAILABLE'
        else:
            row.update(S_first_m2=first['S'], S_second_m2=second['S'],
                       pair_mean_S_m2=(first['S']+second['S'])/2)
        yield row, first, second


def _increment_sum(imu, start, end):
    """Increment i belongs to (t[i-1],t[i]]; use actual partial overlaps."""
    t = imu[:, 0]
    first = max(1, int(np.searchsorted(t, start, side='right')))
    last = int(np.searchsorted(t, end, side='left'))
    left, right = t[first-1:last], t[first:last+1]
    fractions = np.maximum(0., np.minimum(right, end)-np.maximum(left, start))/(right-left)
    return np.sum(imu[first:last+1, 1:4]*fractions[:, None], axis=0)


def _report(group, lag):
    return dict(lag_ms=lag, primary=lag == 1000, candidate_pair_count=len(group),
                supported_pair_count=sum(r['status'] == 'SUPPORTED' for r in group),
                unsupported_reasons=dict(Counter(r['reason'] for r in group if r['reason'])),
                nominal_variance_policy=PAIR_POLICY, variance_ddof=1,
                residual_wrapped=False, residual_trimming=False)


def _scalar_stats(rows, name, length):
    selected = [r for r in rows if r.get(name+'_residual_rad') is not None]
    if len(selected) < 2:
        return {'status': 'UNAVAILABLE_INSUFFICIENT_PAIRS', 'pair_count': len(selected)}
    residuals = np.asarray([r[name+'_residual_rad'] for r in selected], float)
    denominator = float(np.mean([r['S_first_m2']+r['S_second_m2'] for r in selected]))
    variance = float(np.var(residuals, ddof=1))
    if not np.isfinite(residuals).all() or not math.isfinite(variance):
        raise ValueError('Nonfinite scalar residual calibration')
    k2 = variance*length**2/denominator if denominator > 0 else None
    return dict(status='AVAILABLE' if denominator > 0 else 'UNAVAILABLE_ZERO_NOMINAL_VARIANCE',
                pair_count=len(selected), residual_mean_rad=float(residuals.mean()),
                residual_variance_rad2=variance, sigma_rad=math.sqrt(variance/2),
                sigma_deg=math.degrees(math.sqrt(variance/2)), k_squared=k2,
                k=math.sqrt(k2) if k2 is not None else None, mean_endpoint_S_sum_m2=denominator)


def scalar_pair_calibration(*, raw_yaw_rows, pacc1_m, pacc2_m, pvt_flags1,
                            pvt_flags2, baseline_m, imu, rp, window,
                            nominal_variance_policy=PAIR_POLICY):
    """Primary r=unwrapped yaw difference minus installed gyro-z integral."""
    if nominal_variance_policy != PAIR_POLICY:
        raise ValueError('An explicit supported nominal variance policy is required')
    length = _number(baseline_m)
    if length is None or length <= 0: raise ValueError('Baseline length must be positive and finite')
    source, ordered = _sources(raw_yaw_rows, pacc1_m, pacc2_m, pvt_flags1, pvt_flags2, window)
    imu, rp = _array(imu, 7, 'installed IMU increments'), _array(rp, 3, 'frozen roll/pitch')
    diagnostic = _imu_diagnostics(imu, rp)
    times = imu[:, 0]
    # Euler is diagnostic only; excluded singular prefixes cannot poison later pairs.
    cumulative = np.r_[0., np.cumsum(np.where(diagnostic['euler_good'][1:],
                                              diagnostic['euler'][1:], 0.)*np.diff(times))]
    reports, pairs = [], []
    for lag in (1000, 200):
        group = []
        for row, first, second in _pairs(source, ordered, lag, window):
            if row['reason'] is None:
                a, b = first['time'], second['time']
                if not _interval_supported(times, a, b): row['reason'] = 'WHOLE_IMU_INTERVAL_UNAVAILABLE'
                else:
                    delta = second['unwrapped_yaw_rad']-first['unwrapped_yaw_rad']
                    integral = float(_increment_sum(imu, a, b)[2])
                    row.update(status='SUPPORTED', delta_yaw_rad=delta, z_gyro_integral_rad=integral,
                               z_residual_rad=delta-integral, nominal_variance_first_rad2=first['S']/length**2,
                               nominal_variance_second_rad2=second['S']/length**2,
                               euler_residual_rad=None, euler_gyro_integral_rad=None,
                               euler_status='UNAVAILABLE_IMU_RP_INTERVAL')
                    if _interval_supported(times, a, b, diagnostic['euler_good']):
                        euler = float(np.interp(b, times, cumulative)-np.interp(a, times, cumulative))
                        row.update(euler_status='REPORT_ONLY', euler_gyro_integral_rad=euler, euler_residual_rad=delta-euler)
            group.append(row)
        supported = [r for r in group if r['status'] == 'SUPPORTED']
        report = _report(group, lag)
        report.update(primary_method='INSTALLED_GYRO_Z', euler_use='REPORT_ONLY',
                      z=_scalar_stats(supported, 'z', length), euler=_scalar_stats(supported, 'euler', length))
        report['status'] = report['z']['status']
        if supported:
            report['twice_mean_nominal_variance_rad2'] = float(np.mean(
                [r['S_first_m2']+r['S_second_m2'] for r in supported]))/length**2
        reports.append(report); pairs.extend(group)
    return dict(window=list(window), baseline_m=length, method='P12_RAW_5HZ_EXACT_ITOW_PAIRS',
                primary_method='INSTALLED_GYRO_Z', selected_across_sequences=False,
                real_data_claim=False, reports=reports, pairs=pairs)


def _exp_so3(vector):
    v = np.asarray(vector, float)
    theta = float(np.linalg.norm(v)); x, y, z = v
    skew = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    if theta < 1e-8:
        return np.eye(3)+(1-theta**2/6)*skew+(.5-theta**2/24)*(skew@skew)
    return np.eye(3)+(math.sin(theta)/theta)*skew+((1-math.cos(theta))/theta**2)*(skew@skew)


def _cbn(roll, pitch, yaw):
    sr, cr, sp, cp, sy, cy = math.sin(roll), math.cos(roll), math.sin(pitch), math.cos(pitch), math.sin(yaw), math.cos(yaw)
    return np.array([[cp*cy, sr*sp*cy-cr*sy, cr*sp*cy+sr*sy],
                     [cp*sy, sr*sp*sy+cr*cy, cr*sp*sy-sr*cy], [-sp, sr*cp, cr*cp]])


def _vector_stats(rows):
    if len(rows) < 2: return {'status': 'UNAVAILABLE_INSUFFICIENT_PAIRS', 'pair_count': len(rows)}
    residuals = np.asarray([r['residual_ned_m'] for r in rows], float)
    covariance = np.cov(residuals, rowvar=False, ddof=1)
    trace = float(np.trace(covariance))
    mean_s = float(np.mean([r['S_first_m2']+r['S_second_m2'] for r in rows]))
    if not np.isfinite(covariance).all() or not math.isfinite(mean_s):
        raise ValueError('Nonfinite vector residual calibration')
    k2 = trace/(6*mean_s) if mean_s > 0 else None
    return dict(status='AVAILABLE' if mean_s > 0 else 'UNAVAILABLE_ZERO_NOMINAL_VARIANCE',
                pair_count=len(rows), residual_mean_ned_m=residuals.mean(axis=0).tolist(),
                sample_covariance_m2=covariance.tolist(), sample_covariance_trace_m2=trace,
                mean_endpoint_S_sum_m2=mean_s, user_denominator_factor=6,
                k_b_squared=k2, k_b=math.sqrt(k2) if k2 is not None else None)


def vector_pair_calibration(*, raw_yaw_rows, pacc1_m, pacc2_m, pvt_flags1,
                            pvt_flags2, baseline_m, imu, rp, window):
    """r=b2-Cstart Exp(sum(delta_theta_body)) Cstart.T b1; exact user factor 6."""
    if _number(baseline_m) is None or baseline_m <= 0: raise ValueError('Baseline length must be positive and finite')
    source, ordered = _sources(raw_yaw_rows, pacc1_m, pacc2_m, pvt_flags1, pvt_flags2, window)
    imu, rp = _array(imu, 7, 'installed IMU increments'), _array(rp, 3, 'frozen roll/pitch')
    reports, pairs = [], []
    for lag in (1000, 200):
        group = []
        for row, first, second in _pairs(source, ordered, lag, window):
            if row['reason'] is None:
                attitude, good = _rp_at(rp, [first['time']])
                if first['vector'] is None or second['vector'] is None: row['reason'] = 'ENDPOINT_BASELINE_UNAVAILABLE'
                elif not _interval_supported(imu[:, 0], first['time'], second['time']): row['reason'] = 'WHOLE_IMU_INTERVAL_UNAVAILABLE'
                elif not good[0]: row['reason'] = 'START_ROLL_PITCH_UNAVAILABLE'
                else:
                    roll, pitch = attitude[0]
                    cstart = _cbn(float(roll)+math.radians(1.), float(pitch), first['yaw_rad'])
                    increment = _increment_sum(imu, first['time'], second['time'])
                    qn = cstart@_exp_so3(increment)@cstart.T
                    residual = np.asarray(second['vector'])-qn@np.asarray(first['vector'])
                    if not np.isfinite(residual).all(): raise ValueError('Nonfinite vector residual')
                    row.update(status='SUPPORTED', residual_ned_m=residual.tolist(),
                               installed_body_gyro_increment_rad=increment.tolist(), Cstart=cstart.tolist(), Qn=qn.tolist())
            group.append(row)
        report = _report(group, lag)
        report.update(_vector_stats([r for r in group if r['status'] == 'SUPPORTED']))
        reports.append(report); pairs.extend(group)
    return dict(method='D3_VECTOR_EXACT_INSTALLED_GYRO_ROTATION', baseline_m=float(baseline_m),
                window=list(window), variance_ddof=1, user_denominator_factor=6,
                rotation_definition='Cstart Exp(sum actual partial-interval installed body gyro increments) Cstart.T',
                cstart_definition='Rz(raw_yaw) Ry(frozen_pitch) Rx(frozen_roll + 1 degree)',
                residual_definition='b_second - Qn b_first', primary_lag_ms=1000,
                real_data_claim=False, selected_across_sequences=False, reports=reports, pairs=pairs)


def calibration_bin_report(scalar_reports, vector_reports, *, lag_ms=1000):
    """BY2 scalar pair-mean-S linear tertiles; ties lower, empty bins unavailable."""
    if lag_ms not in (1000, 200) or set(scalar_reports) != {'BY2', 'BY2H', 'BY2O'} or set(vector_reports) != set(scalar_reports):
        raise ValueError('S3 requires three explicit scalar/vector reports and a registered lag')
    anchor = [r['pair_mean_S_m2'] for r in scalar_reports['BY2']['pairs'] if r['lag_ms'] == lag_ms and r['status'] == 'SUPPORTED']
    if not anchor: raise ValueError('BY2 has no supported pairs for frozen S3 tertiles')
    edges = np.quantile(np.asarray(anchor, float), [1/3, 2/3], method='linear').tolist()
    scalar_anchor = [r for r in scalar_reports['BY2']['reports'] if r['lag_ms'] == 1000]
    vector_anchor = [r for r in vector_reports['BY2']['reports'] if r['lag_ms'] == 1000]
    if len(scalar_anchor) != 1 or len(vector_anchor) != 1:
        raise ValueError('S3 requires the unique BY2 1 s applied calibration')
    applied_k = scalar_anchor[0]['z'].get('k')
    applied_kb = vector_anchor[0].get('k_b')
    if any(_number(value) is None or value < 0 for value in (applied_k, applied_kb)):
        raise ValueError('S3 applied BY2 calibration is unavailable')
    result = []
    for sequence in ('BY2', 'BY2H', 'BY2O'):
        for family, report in (('scalar', scalar_reports[sequence]), ('vector', vector_reports[sequence])):
            rows = [r for r in report['pairs'] if r['lag_ms'] == lag_ms and r['status'] == 'SUPPORTED']
            for index in range(3):
                selected = [r for r in rows if int(np.searchsorted(edges, r['pair_mean_S_m2'], side='left')) == index]
                stats = _scalar_stats(selected, 'z', report['baseline_m']) if family == 'scalar' else _vector_stats(selected)
                mean_s = float(np.mean([r['pair_mean_S_m2'] for r in selected])) if selected else None
                comparisons = dict(applied_source_sequence='BY2', applied_lag_ms=1000,
                    applied_k=applied_k, applied_k_b=applied_kb, measurement_baseline_m=BASELINE_M,
                    mean_S_bin_m2=mean_s,
                    mean_S_bin_definition='Mean over pairs of (S_first + S_second) / 2',
                    applied_k_sqrt_S_m=applied_k*math.sqrt(mean_s) if mean_s is not None else None,
                    applied_k_b_sqrt_S_m=applied_kb*math.sqrt(mean_s) if mean_s is not None else None,
                    predicted_heading_sigma_deg=math.degrees(applied_k*math.sqrt(mean_s)/BASELINE_M) if mean_s is not None else None,
                    predicted_vector_component_sigma_m=applied_kb*math.sqrt(mean_s) if mean_s is not None else None,
                    empirical_heading_sigma_deg=stats.get('sigma_deg') if family == 'scalar' else None,
                    empirical_vector_component_sigma_m=math.sqrt(stats['sample_covariance_trace_m2']/6)
                        if family == 'vector' and 'sample_covariance_trace_m2' in stats else None,
                    empirical_vector_component_definition='sqrt(trace(sample covariance residual_ned, ddof=1) / 6)',
                    bin_fitted_scales_use='REPORT_ONLY; prediction uses unchanged BY2 1 s applied scales')
                result.append(dict(sequence_id=sequence, family=family, lag_ms=lag_ms,
                                   bin_id=f'S{index+1}', edges_m2=edges, edge_source_sequence='BY2',
                                   pair_mean_S_m2=[r['pair_mean_S_m2'] for r in selected], **stats, **comparisons))
    return dict(boundary_policy='BY2_SCALAR_PAIR_MEAN_S_LINEAR_TERTILES_TIES_TO_LOWER',
                lag_ms=lag_ms, edges_m2=edges, rows=result)
