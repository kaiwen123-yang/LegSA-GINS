"""中文说明：测试 N4H4D evaluator 的 parity 分类入口。"""

from legsa_gins.evaluation.legsa_v23_parity_decision import classify_parity


def test_parity_passed_classification():
    summary = {
        "horizontal_rmse_m": 0.5,
        "up_rmse_m": 1.0,
        "yaw_rmse_deg": 1.9,
        "roll_rmse_deg": 1.2,
        "pitch_rmse_deg": 1.3,
    }
    decision = classify_parity(summary)
    assert decision["parity_classification"] == "parity_passed"
    assert decision["gate_status"]["yaw_gate_pass"] is True
    assert decision["gate_status"]["roll_strict_gate_pass"] is False
    assert decision["gate_status"]["roll_relaxed_gate_pass"] is True


def test_near_gate_yaw_is_not_pass():
    summary = {
        "horizontal_rmse_m": 0.5,
        "up_rmse_m": 1.0,
        "yaw_rmse_deg": 2.1,
        "roll_rmse_deg": 1.2,
        "pitch_rmse_deg": 1.3,
    }
    decision = classify_parity(summary)
    assert decision["parity_classification"] == "parity_near_gate"
    assert decision["parity_candidate"] is False


def test_failed_classification():
    summary = {
        "horizontal_rmse_m": 20.0,
        "up_rmse_m": 1.0,
        "yaw_rmse_deg": 5.0,
        "roll_rmse_deg": 1.2,
        "pitch_rmse_deg": 1.3,
    }
    decision = classify_parity(summary)
    assert decision["parity_classification"] == "parity_failed"
