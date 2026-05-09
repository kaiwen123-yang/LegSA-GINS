"""中文说明：测试 R3A runtime-loop fix decision 映射。"""

from legsa_gins.evaluation.legsa_v23_port_runtime_loop_fix_decision import make_runtime_loop_fix_decision


def test_count_match_goes_to_filter_audit():
    decision = make_runtime_loop_fix_decision(
        {"expected_update_count_min": 10, "expected_update_count_max": 10},
        {"overwritten_before_update_count": 0},
        {"config_ok": True},
        actual_update_count=10,
    )
    assert decision["update_count_issue"] is False
    assert decision["recommended_next_stage"] == "N4H4R3B_filter_residual_covariance_gap_audit"


def test_overwritten_maps_to_runtime_fix():
    decision = make_runtime_loop_fix_decision(
        {"expected_update_count_min": 10, "expected_update_count_max": 10},
        {"overwritten_before_update_count": 3},
        {"config_ok": True},
        actual_update_count=5,
    )
    assert decision["recommended_next_stage"] == "N4H4R3B_runtime_loop_gnss_queue_fix"


def test_config_issue_maps_to_config_fix():
    decision = make_runtime_loop_fix_decision(
        {"expected_update_count_min": 10, "expected_update_count_max": 10},
        {"overwritten_before_update_count": 0},
        {"config_ok": False, "config_start_end_too_short": True},
        actual_update_count=10,
    )
    assert decision["recommended_next_stage"] == "N4H4R3B_config_start_end_fix"
