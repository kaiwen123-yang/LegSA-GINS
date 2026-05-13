"""中文说明：测试 N8A1 决策优先级。"""

from legsa_gins.fgo.fgo_n8a1_decision import make_n8a1_decision


def test_n8a1_decision_prioritizes_yaw_convention_blocker() -> None:
    decision = make_n8a1_decision(
        yaw_convention={"blocker_status": "yaw_wrap_residual_blocker", "yaw_delta_rmse_after_best_wrap": 80.0},
        state_epoch_mapping={"blocker_status": "clear"},
        factor_policy={"candidate_factor_leak_suspect": False, "smoothness_weight_suspect": True, "yaw_factor_weight_suspect": True},
        yaw_diagnostics={"primary_hypothesis": "yaw_wrap_or_residual_convention", "yaw_delta_rmse_wrapped_deg": 80.0},
        ablation={"best_yaw_delta_variant": "no_smoothness", "best_yaw_delta_rmse_deg": 0.0},
        figures={"required_figures_generated": True, "required_figures_nonempty": True, "figure_count_total": 10},
    )
    assert decision["status"] == "fgo_yaw_convention_blocker"
    assert decision["recommended_next_stage"] == "N8A2_yaw_convention_fix"
    assert decision["fgo_output_feedback_to_ekf"] is False
