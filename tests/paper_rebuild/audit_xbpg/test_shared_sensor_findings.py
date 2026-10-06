"""Original shared sensor functions with synthetic fixtures, no legacy runner.

Strict xfails preserve confirmed defects; passing tests delimit correct behavior
or demonstrate a documented approximation rather than claiming sensor truth.
"""
import csv
import math

import pytest

from legsa_gins.frames.conventions import FrameName
from legsa_gins.frames.go2_adapter import Go2FrameAdapter
from legsa_gins.frames.quaternion import quat_normalize, quat_rotate_vector
from legsa_gins.frames.transforms import enu_to_ned, flu_to_frd
from legsa_gins.time_alignment import event_normalization as events
from legsa_gins.time_alignment.time_domain_audit import infer_time_domain, TimeDomainType
from legsa_gins.datasets.by2.unitree_imu_semantics import make_unitree_imu_semantics_report


def write_rows(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def test_normal_quaternion_rotation_is_active_hamilton_wxyz():
    q = (math.sqrt(.5), 0., 0., math.sqrt(.5))
    assert quat_rotate_vector(q, (1., 0., 0.)) == pytest.approx((0., 1., 0.), abs=1e-14)


def test_flu_frd_and_enu_ned_are_proper_rotations():
    # These are rotations, not sensor installation calibrations.
    for transform in (flu_to_frd, enu_to_ned):
        assert transform(transform((1., 2., 3.))) == (1., 2., 3.)
        assert math.dist(transform((1., 2., 3.)), (0., 0., 0.)) == math.sqrt(14.)
        x, y, z = [transform(basis) for basis in ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))]
        cross_xy = (x[1]*y[2]-x[2]*y[1], x[2]*y[0]-x[0]*y[2], x[0]*y[1]-x[1]*y[0])
        assert cross_xy == z


@pytest.mark.parametrize('scale', [1e200, 1e-200])
@pytest.mark.xfail(strict=True, reason='SS-01: direct squared norm over/underflows for finite nonzero quaternion')
def test_finite_scaled_identity_quaternion_normalizes(scale):
    assert quat_normalize((scale, 0., 0., 0.)) == (1., 0., 0., 0.)


@pytest.mark.xfail(strict=True, reason='SS-01: nonfinite quaternion is not rejected')
def test_nonfinite_quaternion_rejected():
    with pytest.raises(ValueError):
        quat_normalize((math.nan, 0., 0., 0.))


@pytest.mark.xfail(strict=True, reason='SS-02: FRD passthrough skips the shape check performed by FLU path')
def test_frd_adapter_rejects_wrong_dimension():
    with pytest.raises(ValueError):
        Go2FrameAdapter().adapt_body_vector_to_frd((1., 2.), input_frame=FrameName.IMU_FRD_COMPATIBLE)


@pytest.mark.xfail(strict=True, reason='SS-03: infinity is classified as Unix-like time')
def test_nonfinite_time_is_not_unix_epoch_evidence():
    assert infer_time_domain([math.inf, math.inf])['time_domain'] == TimeDomainType.UNKNOWN


@pytest.mark.xfail(strict=True, reason='SS-03: NaN passes both clipping comparisons and is written as algo time')
def test_event_time_export_does_not_accept_nan(tmp_path):
    source = tmp_path / 'input.csv'
    write_rows(source, [{'timestamp': 'nan'}])
    result = events.add_algo_time_to_csv(source, tmp_path / 'output.csv', raw_time_field='timestamp', start_time=1.)
    assert result == []


@pytest.mark.xfail(strict=True, reason='SS-04: common window only uses maxima and invents start support at zero')
def test_disjoint_algorithm_times_do_not_yield_common_window():
    report = events.compute_common_algorithm_window(
        [{'algo_time_sec': 100.}, {'algo_time_sec': 110.}],
        [{'algo_time_sec': 0.}, {'algo_time_sec': 10.}], end_margin_sec=0.)
    assert report['evidence_status'] != 'common_window_ready'


@pytest.mark.xfail(strict=True, reason='SS-05: valid latitude zero is replaced by initial latitude through or fallback')
def test_motion_detector_preserves_valid_zero_latitude(tmp_path):
    path = tmp_path / 'gnss.csv'
    rows = [dict(has_position=1, heading_valid=0, lat_deg=.001 if i == 0 else 0.,
                 lon_deg=1., time_unix=i, tow=i) for i in range(4)]
    write_rows(path, rows)
    report = events.detect_gnss_formal_motion_start(path)
    assert report['evidence_status'] == 'detected'
    assert report['gnss_formal_start_raw_time'] == 1.


@pytest.mark.xfail(strict=True, reason='SS-06: tow fallback is mislabeled time_unix')
def test_tow_fallback_reports_its_actual_time_domain(tmp_path):
    path = tmp_path / 'gnss.csv'
    write_rows(path, [dict(has_position=1, heading_valid=1, lat_deg=30., lon_deg=120., tow=100+i) for i in range(4)])
    report = events.detect_gnss_formal_motion_start(path)
    assert report['gnss_time_type'] == 'tow'


@pytest.mark.xfail(strict=True, reason='SS-07: all missing quaternion checks yield aggregate passed')
def test_missing_imu_semantic_evidence_cannot_pass():
    report = make_unitree_imu_semantics_report([{'timestamp': 1.}])
    assert report['quaternion_rpy_consistency_status'] == 'evidence_missing'


def test_maintained_kick_threshold_above_min_score_has_no_effect(tmp_path):
    path = tmp_path / 'go2.csv'
    write_rows(path, [dict(timestamp=i, gyro_x=12. if i == 1 else 0.,
                           gyro_y=0., gyro_z=0., acc_x=0., acc_y=0., acc_z=9.80665)
                     for i in range(5)])
    default = events.detect_go2_kick_event(path)
    much_higher = events.detect_go2_kick_event(path, zscore_threshold=1e6)
    assert default == much_higher
    assert default['kick_score'] == 4.
    assert default['evidence_status'] == 'detected'


def test_stationary_heading_valid_is_motion_start_candidate(tmp_path):
    path = tmp_path / 'gnss.csv'
    write_rows(path, [dict(has_position=1, heading_valid=1, lat_deg=30., lon_deg=120.,
                           time_unix=100+i, tow=100+i) for i in range(4)])
    report = events.detect_gnss_formal_motion_start(path)
    assert report['evidence_status'] == 'detected'
    assert report['gnss_formal_start_raw_time'] == 101.
