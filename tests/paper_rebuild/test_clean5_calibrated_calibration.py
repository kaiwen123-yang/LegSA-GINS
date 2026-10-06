"""Isolated mathematical inputs only; never create synthetic real-data tables."""
import math
import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean5_calibrated.calibration import (
    attitude_at, body_to_ned, calibrate_arrays, fit_axis,
)


def artificial_inputs(duration=240.):
    # Unit-test arrays have no repository raw/provider/result roles.
    it = np.arange(1, int(duration*20)+1)/20
    pt = np.arange(int(duration*5)+1)/5
    return dict(imu_times_s=it, imu_dvel_mps=np.tile([0, 0, -.49], (len(it), 1)),
                imu_dt_s=np.full(len(it), .05), rpy_times_s=[0., duration],
                roll_pitch_rad=[[0, 0], [0, 0]], a1_times_s=np.arange(int(duration)+1),
                yaw_rad=np.zeros(int(duration)+1), pvt_itow_ms=np.arange(len(pt), dtype=np.int64)*200,
                pvt_times_s=pt, pvt_velocity_mps=np.zeros((len(pt), 3)),
                window=[0., duration], g_local_mps2=9.8)


def test_frd_to_ned_rotation_and_unwrap_no_pitch_flip():
    r = body_to_ned(.1, .2, .3)
    from legsa_gins.input_generation.imu_txt_builder import euler_rpy_deg_to_matrix
    np.testing.assert_allclose(r, euler_rpy_deg_to_matrix(*np.rad2deg([.1, .2, .3])), atol=1e-15)
    c, valid = attitude_at([.5], [0, 1], [[0, .2], [0, .2]], [0, 1], np.deg2rad([179, -179]))
    np.testing.assert_allclose(c[0], body_to_ned(0, .2, math.pi), atol=1e-15)
    assert valid.tolist() == [True]


def test_a1_gap_endpoints_only_and_no_extrapolation():
    _, support = attitude_at([-.1, 0, .5, 1, 1.1, 2, 3, 3.1],
                             [0, 4], [[0, 0], [0, 0]], [0, 1, 3], [0, 0, 0])
    assert support.tolist() == [False, True, True, True, False, False, True, False]


def test_ols_units_intercept_and_axis_fallback():
    fit = fit_axis([.2, .4, 1, 2], [.0034, .0038, .005, .007], [0., .01, .02, .03], .077, 77.8)
    assert fit['status'] == 'CALIBRATED'
    assert fit['q_m2ps3'] == pytest.approx(.002)
    assert fit['c_m2ps2'] == pytest.approx(.003)
    assert fit['vrw_mps_sqrt_hour'] == pytest.approx(math.sqrt(.002)*60)
    assert fit['abstd_mGal'] == pytest.approx(np.std([0, .01, .02, .03], ddof=1)*1e5)
    negc = fit_axis([1, 2], [0, 1], [0, 1, 2], .077, 77.8)
    assert negc['c_m2ps2'] == pytest.approx(-1)
    for x, y, means, reason in [([1, 2], [2, 1], [0, 1, 2], 'NONPOSITIVE_Q'),
                                ([1, 2], [1, 2], [0, 1], 'FEWER_THAN_THREE_NONEMPTY_WINDOWS')]:
        fit = fit_axis(x, y, means, .077, 77.8)
        assert fit['status'] == 'FALLBACK' and reason in fit['fallback_reasons']
        assert fit['vrw_mps_sqrt_hour'] == .077 and fit['abstd_mGal'] == 77.8


def test_exact_itow_pairs_no_second_dt_and_full_windows():
    data = artificial_inputs(274.)
    summary, rows, variances, windows = calibrate_arrays(**data)
    accepted = [r for r in rows if r['status'] == 'ACCEPTED']
    # Small prefix-sum roundoff is allowed. An extra dt or gravity scale is not.
    assert max(abs(r['residual_down_mps']) for r in accepted) < 1e-8
    assert all(r['sample_count'] == 0 and r['status'] == 'UNAVAILABLE'
               for r in variances if r['lag_ms'] == 1500)
    assert summary['complete_bias_window_count'] == 4
    assert summary['unused_partial_bias_window_s'] == [240., 274.]
    assert {(r['window_start_s'], r['window_end_s']) for r in windows} == {(0.,60.),(60.,120.),(120.,180.),(180.,240.)}
    assert {r['sample_count'] for r in windows} == {296}


def test_gap_crossing_pairs_are_unavailable_and_preserved_in_ledger():
    data = artificial_inputs(4.)
    data.update(a1_times_s=[0., 1., 3., 4.], yaw_rad=[0., 0., 0., 0.])
    summary, rows, _, _ = calibrate_arrays(**data)
    crossing = [r for r in rows if r['start_time_s'] < 3 and r['end_time_s'] > 1]
    assert crossing and all(r['status'] == 'UNAVAILABLE_ATTITUDE_OR_IMU_SUPPORT' for r in crossing)
    assert summary['a1_gap_intervals_s'] == [[1., 3.]]


def test_preserves_imu_gap_coverage_without_filling_or_residual_selection():
    data = artificial_inputs(4.)
    keep = data['imu_times_s'] != 2.
    for key in ('imu_times_s', 'imu_dvel_mps', 'imu_dt_s'):
        data[key] = data[key][keep]
    _, rows, _, _ = calibrate_arrays(**data)
    row = next(r for r in rows if r['lag_ms'] == 1000 and r['start_time_s'] == 1.)
    assert row['status'] == 'ACCEPTED'
    assert row['imu_dt_covered_s'] == pytest.approx(.95)
    assert row['residual_down_mps'] == pytest.approx(.49)


def test_integer_itow_and_positive_measured_dt_required():
    data = artificial_inputs(4.)
    data['pvt_itow_ms'] = data['pvt_itow_ms'].astype(float)
    with pytest.raises(ValueError, match='integer'):
        calibrate_arrays(**data)
    data = artificial_inputs(4.)
    data['imu_dt_s'][0] = 0
    with pytest.raises(ValueError, match='dt'):
        calibrate_arrays(**data)


def test_all_fallback_has_explicit_stop_status():
    summary, _, _, _ = calibrate_arrays(**artificial_inputs(4.))
    assert summary['status'] == 'STOP_ALL_AXES_FALLBACK'
    assert summary['vrw'] == [.077]*3 and summary['abstd'] == [77.8]*3


def test_strict_io_audit_forbidden_attempts_and_undeclared_reads(tmp_path):
    from legsa_gins.paper_rebuild.clean5_calibrated.calibration_runner import strict_open_audit
    raw, clean = tmp_path/'raw', tmp_path/'clean'
    output, allowed = clean/'own', raw/'observation.csv'
    def row(path, flags='O_RDONLY', rc=3):
        return {'path': str(path), 'flags': flags, 'return_code': rc}
    kwargs = dict(raw_root=raw, clean_root=clean, output_root=output, input_paths=[allowed])
    good = [row(allowed), row('/usr/lib/python3.10/traceback.py'), row(output/'result.csv', 'O_WRONLY|O_CREAT')]
    assert strict_open_audit(good, **kwargs)['pass']
    for bad in [row(raw/'trace_reference.csv'), row(raw/'archive.bag', rc=-1), row(raw/'a.fpl'),
                row(clean/'previous'/'result.csv'), row(raw/'other_sequence.txt'),
                row(clean/'outside.json', 'O_WRONLY|O_CREAT')]:
        assert not strict_open_audit(good+[bad], **kwargs)['pass']
    symlink = row(allowed)
    symlink['lexical_path'] = str(raw/'trace_reference.csv')
    assert not strict_open_audit(good+[symlink], **kwargs)['pass']


def test_input_hash_failure_precedes_raw_parse(tmp_path):
    from types import SimpleNamespace
    from legsa_gins.paper_rebuild.clean5_calibrated.calibration_runner import verify_input_pins, INPUT_ROLES
    path = tmp_path/'input.csv'
    path.write_text('test fixture,not actual data\n')
    spec = {'inputs': {k: {'path': str(path), 'sha256': '0'*64} for k in INPUT_ROLES}}
    registry = SimpleNamespace(code_root=tmp_path, raw_root=tmp_path/'raw', clean_root=tmp_path/'clean')
    with pytest.raises(ValueError, match='hash mismatch'):
        verify_input_pins(spec, registry)


def test_input_epoch_join_and_measured_dt_mapping(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean5_calibrated import calibration_runner as runner
    base = 315964782
    times = np.arange(81)/20
    frames = []
    for t in times:
        stamp_value = base+t
        sec = int(stamp_value)
        row = {'stamp_sec': sec, 'stamp_nanosec': round((stamp_value-sec)*1e9),
               'timestamp': stamp_value, 'roll_rad': .1, 'pitch_rad': .2}
        row.update({k: .0 for k in ('gyro_x', 'gyro_y', 'gyro_z', 'acc_x', 'acc_y', 'acc_z')})
        frames.append(row)
    monkeypatch.setattr(runner, 'parse_go2_body_state_text', lambda path: frames)
    paths = {key: tmp_path/key for key in ('go2_body', 'imu_increment', 'status', 'a1', 'pvt_raw', 'gnss_v2')}
    ft = np.array([r['stamp_sec']+r['stamp_nanosec']*1e-9 for r in frames])
    paths['imu_increment'].write_text(''.join(format(float(format(t-base, '.12g')), '.6f')+' 0 0 0 0 0 -.49\n' for t in ft[1:]))
    status = [{'header.stamp.secs': str(base+i), 'header.stamp.nsecs': '0',
               'time_gps_wno': '0', 'time_gps_tow': str(i)} for i in range(5)]
    a1 = [{'source_timestamp': str(base+i), 'body_yaw_ned_deg': '1.0', 'yaw_std_deg': '1.5'} for i in range(5)]
    monkeypatch.setattr(runner, 'csv_rows', lambda path: status if path == paths['status'] else a1)
    pvt = {i*1000: {'velocity_mps': [1., 2., 3.]} for i in range(5)}
    monkeypatch.setattr(runner, 'decode_receiver', lambda path: ({}, pvt))
    gnss = np.zeros((5, 18))
    gnss[:, 0] = np.arange(5)
    gnss[:, 7:10] = [1, 2, 3]
    gnss[:, 13:15] = [1, 1.5]
    gnss[:, 15:] = 1
    np.savetxt(paths['gnss_v2'], gnss)
    spec = dict(base_time=base, window_seconds=[0., 4.], g_local_mps2=9.8,
                frozen_vrw=[.077]*3, frozen_abstd=[77.8]*3,
                fit={'lag_milliseconds': [200, 1000]}, orientation={'maximum_a1_gap_seconds': 1.2})
    arrays, audit = runner.load_arrays(paths, spec)
    assert audit['same_epoch_rv_identity'] and audit['imu_timestamp_token_identity']
    np.testing.assert_array_equal(arrays['imu_dt_s'], np.diff(ft))
    np.testing.assert_array_equal(arrays['imu_dvel_mps'][:, 2], np.full(80, -.49))
    np.testing.assert_allclose(arrays['roll_pitch_rad'], np.tile([.1, .2], (81, 1)))
    assert arrays['a1_times_s'].tolist() == [0., 1., 2., 3., 4.]
    a1[0]['source_timestamp'] = str(base+.25)
    with pytest.raises(ValueError, match='missing from status'):
        runner.load_arrays(paths, spec)
