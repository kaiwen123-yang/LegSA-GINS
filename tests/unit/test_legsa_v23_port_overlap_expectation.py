"""中文说明：测试有效 overlap 期望更新数，不使用 total GNSS rows。"""

from legsa_gins.evaluation.legsa_v23_port_overlap_expectation import (
    classify_update_count,
    compute_overlap_expectation,
)


def test_overlap_rows_ignore_outside_window():
    imu = [10.0, 11.0, 12.0, 13.0]
    gnss = [0.0, 10.5, 11.5, 12.5, 20.0]
    report = compute_overlap_expectation(imu, gnss, 10.0, 13.0)
    assert report["gnss_count"] == 5
    assert report["gnss_rows_in_overlap"] == 3
    assert report["expected_update_count_min"] == 3


def test_short_imu_duration_vs_long_gnss_duration():
    report = compute_overlap_expectation([100.0, 101.0], [1.0, 100.5, 101.5, 200.0], 0.0, 0.0)
    assert report["gnss_rows_in_overlap"] == 1
    assert report["gnss_rows_after_last_imu"] == 2


def test_classify_count_low_uses_overlap_not_total():
    report = {"expected_update_count_min": 3, "expected_update_count_max": 3}
    assert classify_update_count(report, 3)["update_count_low"] is False
    assert classify_update_count(report, 1)["update_count_low"] is True
