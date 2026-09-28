"""HX-03 cache-only chronological adapter; trace mode is always disabled."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import traceback

import numpy as np

from ..horizontal_literature.ext05_pavlasek import METHOD_IEKF, METHOD_SINGLE, ExtendedPose, PavlasekIEKF
from ..horizontal_literature.ext05_provider import (
    BASELINE_BODY_FRD_M, LEVER_IMU_TO_RECEIVER1_FRD_M, initial_attitude_from_gravity_and_baseline,
)
from ..horizontal_literature.phase5_runner import (
    NAV_FIELDS, INNOVATION_FIELDS, NIS_FIELDS, _load_cache, _append_nav, _write_csv,
)
from .ext05_sequence_runner import _nav_row, _h02_gnss_update, materialize_exact_evaluator_nav
from .hx03_relative_update import scheduled_update
from .hx03_injection import BASE_TIME, write_json, sha
from .parameters import load_parameters, scaled_frd_specific_force


class Diverged(RuntimeError):
    pass


def bounds(filter_, initial_position):
    p, v = filter_.pose.position_ned_m, filter_.pose.velocity_ned_mps
    if not all(np.isfinite(x).all() for x in (p, v, filter_.pose.C_nb, filter_.covariance)):
        raise Diverged('D8 nonfinite state or covariance')
    displacement = p - initial_position
    if np.linalg.norm(displacement) > 10000 or np.linalg.norm(v) > 50 or abs(displacement[2]) > 1000:
        raise Diverged('D8 displacement>10000m, speed>50m/s or height excursion>1000m')


def run(cache, output, method, parameter_path):
    """Same PHASE5/H-EXT-01 event order, initialization, hold and arithmetic."""
    output.mkdir(parents=True, exist_ok=False)
    parameters = load_parameters(parameter_path)
    arrays, manifest = _load_cache(cache)
    calibration = manifest['calibration']
    solution_times, imu_times = arrays['solution_times'], arrays['imu_times']
    two_receiver = method != 'EXT05C'
    candidates = np.flatnonzero((solution_times >= float(calibration['end_time_unix_seconds']))
                               & arrays['valid1'] & arrays['valid2'] & (solution_times <= imu_times[-1]))
    if not candidates.size:
        raise RuntimeError('no valid static-initialization solution epoch')
    initial_index = int(candidates[0])
    initial_time = float(solution_times[initial_index])
    attitude, attitude_audit = initial_attitude_from_gravity_and_baseline(
        calibration['mean_specific_force_frd_mps2'], arrays['p2'][initial_index] - arrays['p1'][initial_index])
    initial_position = arrays['p1'][initial_index] - attitude @ LEVER_IMU_TO_RECEIVER1_FRD_M
    filter_ = PavlasekIEKF(
        ExtendedPose(attitude, np.zeros(3), initial_position),
        np.diag([math.radians(60.0) ** 2] * 3 + [0.1**2] * 3 + [0.1**2] * 3),
        receiver1_from_imu_body_m=LEVER_IMU_TO_RECEIVER1_FRD_M,
        receiver2_from_receiver1_body_m=BASELINE_BODY_FRD_M,
        gyro_psd=parameters.gyro_psd_rad2_s, accelerometer_psd=parameters.accel_psd_m2_s3,
        gravity_ned_mps2=[0.0, 0.0, float(calibration['local_gravity_mps2'])], two_receiver=two_receiver)
    previous_imu_index = int(np.searchsorted(imu_times, initial_time, side='right') - 1)
    if previous_imu_index < 0:
        raise RuntimeError('initial position precedes Go2 IMU')
    gyro_bias = np.asarray(calibration['gyro_bias_frd_radps'], dtype=float)
    current_gyro = np.asarray(arrays['gyro'][previous_imu_index], dtype=float) - gyro_bias
    current_accel = scaled_frd_specific_force(np.asarray(arrays['accel'][previous_imu_index], dtype=float), parameters.accel_scale)
    imu_index, solution_index = previous_imu_index + 1, initial_index + 1
    state_time = initial_time
    method_id = METHOD_IEKF if two_receiver else METHOD_SINGLE
    nav, innovations, nis = [], [], []
    _append_nav(nav, _nav_row(method_id, state_time, filter_, base_time=BASE_TIME))
    processed, invalid, relative_count = 1, 0, 0
    failure = None
    try:
        while imu_index < len(imu_times):
            next_imu = float(imu_times[imu_index])
            next_solution = (float(solution_times[solution_index]) if solution_index < len(solution_times)
                             and float(solution_times[solution_index]) <= float(imu_times[-1]) else math.inf)
            event_time = min(next_imu, next_solution)
            dt = event_time - state_time
            if dt < -1.0e-9:
                raise RuntimeError('recursive event stream is nonchronological')
            if dt > 1.0e-12:
                filter_.propagate(current_gyro, current_accel, dt)
                state_time = event_time
                bounds(filter_, initial_position)
            if next_imu <= event_time + 1.0e-9:
                current_gyro = np.asarray(arrays['gyro'][imu_index], dtype=float) - gyro_bias
                current_accel = scaled_frd_specific_force(np.asarray(arrays['accel'][imu_index], dtype=float), parameters.accel_scale)
                imu_index += 1
            if next_solution <= event_time + 1.0e-9:
                index = solution_index
                solution_index += 1
                relative = method == 'LC01-BR' and bool(arrays['relative_only'][index])
                callback = None
                if relative:
                    callback = lambda p1, R1, **kw: scheduled_update(filter_, p1, R1, relative_only=True, **kw)
                accepted = _h02_gnss_update(filter_, arrays, index, state_time=state_time, base_time=BASE_TIME,
                    two_receiver=two_receiver, method_id=method_id, innovation_rows=innovations, nis_rows=nis,
                    measurement_update=callback)
                processed += int(accepted)
                invalid += int(not accepted)
                relative_count += int(accepted and relative)
                bounds(filter_, initial_position)
            _append_nav(nav, _nav_row(method_id, state_time, filter_, base_time=BASE_TIME))
    except Exception as exc:
        traceback.print_exc()
        classification = 'ALGORITHM_FAILURE_DIVERGED' if isinstance(exc, Diverged) else 'ABNORMAL_EXIT'
        try:
            bounds(filter_, initial_position)
        except Diverged:
            classification = 'ALGORITHM_FAILURE_DIVERGED'
        failure = {'failure_class': classification, 'exception': type(exc).__name__, 'message': str(exc),
                   'time_seconds': state_time - BASE_TIME, 'last_retained_time_seconds': nav[-1]['time_seconds']}
    _write_csv(output / 'NAV.csv', NAV_FIELDS, nav)
    _write_csv(output / 'INNOVATION.csv', INNOVATION_FIELDS, innovations)
    _write_csv(output / 'NIS.csv', NIS_FIELDS, nis)
    adapter = None
    supported = sum(66 <= row['time_seconds'] <= 340 for row in nav)
    if supported >= 2:
        adapter = materialize_exact_evaluator_nav(output / 'NAV.csv', output / 'EXACT_EVALUATOR_INPUT.nav',
            origin_ecef_m=manifest['origin_ecef_m'], ecef_to_ned=manifest['ecef_to_ned'],
            base_time=BASE_TIME, window=(66., 340.))
    result = {'method': method, 'method_label': '改动过的 LC01' if method == 'LC01-BR' else method,
              'status': 'FAILED' if failure else 'COMPLETED', 'failure': failure,
              'trace_mode': 'disabled', 'reference_opens': 0,
              'initial_solution_index': initial_index, 'initial_time': initial_time,
              'initial_attitude_audit': attitude_audit, 'processed_solution_count': processed,
              'invalid_solution_count': invalid, 'relative_only_update_count': relative_count,
              'adapter': adapter, 'cache_manifest_sha256': sha(cache / 'CACHE_MANIFEST.json')}
    write_json(output / 'NATIVE_RESULT.json', result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--method', choices=['LC01', 'EXT05C', 'LC01-BR'], required=True)
    p.add_argument('--parameters', type=Path, required=True)
    p.add_argument('--trace-mode', choices=['disabled'], required=True)
    a = p.parse_args()
    result = run(a.cache, a.output, a.method, a.parameters)
    print(json.dumps({'status': result['status'], 'failure': result['failure']}), flush=True)
    return 0 if result['status'] == 'COMPLETED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
