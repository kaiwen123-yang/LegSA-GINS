"""中文说明：coverage report 测试只检查输入构造行覆盖，不代表性能评价。"""

import pytest

from legsa_gins.input_generation.process_data_coverage import (
    make_process_data_coverage_report,
    validate_process_data_coverage_report,
)


def test_coverage_report_passed_for_status_retention():
    report = make_process_data_coverage_report(
        status_base_row_count=10,
        pvt_velocity_row_count=2,
        yaw_row_count=9,
        gnss_output_row_count=10,
        pvt_merge_match_count_before_fill=2,
        yaw_merge_match_count_before_fill=9,
        dropna_count=0,
    )

    assert report["coverage_status"] == "passed"
    assert report["output_to_status_ratio"] == 1.0
    assert report["output_to_yaw_ratio"] > 1.0
    assert validate_process_data_coverage_report(report) is True


def test_coverage_report_flags_pvt_master_regression():
    report = make_process_data_coverage_report(
        status_base_row_count=10,
        pvt_velocity_row_count=2,
        yaw_row_count=9,
        gnss_output_row_count=2,
        pvt_merge_match_count_before_fill=2,
        yaw_merge_match_count_before_fill=2,
        dropna_count=8,
    )

    assert report["coverage_status"] == "suspicious"
    assert report["coverage_warning"]


def test_coverage_report_validates_status():
    report = make_process_data_coverage_report(
        status_base_row_count=10,
        pvt_velocity_row_count=2,
        yaw_row_count=9,
        gnss_output_row_count=10,
        pvt_merge_match_count_before_fill=2,
        yaw_merge_match_count_before_fill=9,
        dropna_count=0,
    )
    report["coverage_status"] = "made_up"
    with pytest.raises(ValueError, match="Unsupported coverage_status"):
        validate_process_data_coverage_report(report)
