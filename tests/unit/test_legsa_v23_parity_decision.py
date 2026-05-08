"""中文说明：测试 N4H4D parity decision 的 claim 边界。"""

from legsa_gins.evaluation.legsa_v23_parity_decision import classify_parity, make_decision


def test_no_performance_claim_flags():
    decision = make_decision(
        {
            "horizontal_rmse_m": 0.5,
            "up_rmse_m": 1.0,
            "yaw_rmse_deg": 1.9,
            "roll_rmse_deg": 1.2,
            "pitch_rmse_deg": 1.3,
        }
    )
    assert decision["paper_performance_claim_allowed"] is False
    assert decision["proposed_factor_claim_allowed"] is False
    assert decision["numerical_performance_claim"] is False


def test_roll_pitch_relaxed_not_strict():
    decision = classify_parity(
        {
            "horizontal_rmse_m": 0.5,
            "up_rmse_m": 1.0,
            "yaw_rmse_deg": 1.9,
            "roll_rmse_deg": 1.2,
            "pitch_rmse_deg": 1.3,
        }
    )
    assert decision["gate_status"]["roll_relaxed_gate_pass"] is True
    assert decision["gate_status"]["roll_strict_gate_pass"] is False
    assert decision["roll_pitch_relaxed_not_strict"] is True


def test_yaw_greater_than_two_is_not_pass():
    decision = classify_parity(
        {
            "horizontal_rmse_m": 0.5,
            "up_rmse_m": 1.0,
            "yaw_rmse_deg": 2.01,
            "roll_rmse_deg": 1.2,
            "pitch_rmse_deg": 1.3,
        }
    )
    assert decision["gate_status"]["yaw_gate_pass"] is False
    assert decision["yaw_over_2_allowed_as_pass"] is False
    assert decision["parity_classification"] == "parity_near_gate"
