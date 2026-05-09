"""中文说明：测试 R3 parity decision 的工程边界和 external clean 阈值。"""

from legsa_gins.evaluation.legsa_v23_port_parity_decision import make_port_parity_decision


def test_parity_passed_is_engineering_only():
    summary = {
        "horizontal_rmse_m": 0.5,
        "up_rmse_m": 1.0,
        "yaw_rmse_deg": 1.9,
        "roll_rmse_deg": 1.2,
        "pitch_rmse_deg": 1.4,
    }
    decision = make_port_parity_decision(summary, {})
    assert decision["parity_classification"] == "parity_passed"
    assert decision["engineering_backbone_parity_only"] is True
    assert decision["paper_performance_claim"] is False
    assert decision["proposed_factor_claim"] is False


def test_yaw_gt_two_is_near_not_pass():
    summary = {
        "horizontal_rmse_m": 0.5,
        "up_rmse_m": 1.0,
        "yaw_rmse_deg": 2.05,
        "roll_rmse_deg": 1.2,
        "pitch_rmse_deg": 1.4,
    }
    decision = make_port_parity_decision(summary, {})
    assert decision["parity_classification"] == "parity_near_gate"


def test_external_threshold_failure():
    summary = {
        "horizontal_rmse_m": 1.9,
        "up_rmse_m": 1.0,
        "yaw_rmse_deg": 1.9,
        "roll_rmse_deg": 1.2,
        "pitch_rmse_deg": 1.4,
    }
    decision = make_port_parity_decision(summary, {"recommended_next_stage": "N4H4R3_filter_math_gap_fix"})
    assert decision["parity_classification"] == "parity_failed"
    assert decision["recommended_next_stage"] == "N4H4R3_filter_math_gap_fix"
