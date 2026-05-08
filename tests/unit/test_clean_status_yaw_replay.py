"""中文说明：N4H2G clean replay 单元测试只检查 clean policy 合同。"""

from legsa_gins.evaluation.clean_status_yaw_replay import DEFAULT_CLEAN_POLICY


def test_clean_policy_has_no_noise_outlier_or_outage() -> None:
    assert DEFAULT_CLEAN_POLICY["yaw_source_mode"] == "status"
    assert DEFAULT_CLEAN_POLICY["yaw_std_mode"] == "fixed_1p5"
    assert DEFAULT_CLEAN_POLICY["yaw_noise_std_deg"] == 0.0
    assert DEFAULT_CLEAN_POLICY["outlier_mode"] == "none"
    assert DEFAULT_CLEAN_POLICY["outlier_ratio"] == 0.0
    assert DEFAULT_CLEAN_POLICY["enable_outage"] is False
    assert DEFAULT_CLEAN_POLICY["trace_yaw_for_solver"] is False
    assert DEFAULT_CLEAN_POLICY["output_only_correction"] is False
