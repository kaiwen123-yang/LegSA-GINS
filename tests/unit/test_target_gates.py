"""中文说明：target gates 只控制 diagnostic ready 状态。"""

from legsa_gins.evaluation.target_gates import evaluate_target_gates


def test_bad_metrics_not_ready_for_factor_stacking():
    report = evaluate_target_gates(
        {
            "horizontal_rmse_m": 100.0,
            "up_rmse_m": 20.0,
            "yaw_rmse_deg": 30.0,
            "roll_rmse_deg": 2.0,
            "pitch_rmse_deg": 2.0,
        }
    )

    assert report["target_gate_pass"] is False
    assert report["ready_for_factor_stacking"] is False
    assert report["gates"]["horizontal_rmse_m"] == 2.0

