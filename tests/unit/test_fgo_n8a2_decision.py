"""中文说明：测试 N8A2 决策规则。"""

from legsa_gins.fgo.fgo_n8a2_decision import make_n8a2_decision


def test_n8a2_decision_ready_when_wrapped_yaw_improves() -> None:
    decision = make_n8a2_decision(
        contract={"dual_yaw_wrap": True, "smoothness_wrap": True, "yaw_rate_wrap": True},
        regression={"all_tests_passed": True},
        variant_summary={
            "variants": [
                {"variant": "yaw_wrap_fixed_default_active_stack", "yaw_delta_wrapped_rmse_deg": 2.0, "yaw_delta_raw_rmse_deg": 2.0, "final_cost": 1.0},
                {"variant": "yaw_wrap_fixed_no_smoothness_diagnostic", "yaw_delta_wrapped_rmse_deg": 0.0},
            ]
        },
        comparison={"yaw_delta_wrapped_improvement_deg": 10.0, "gross_degradation": False, "n8a_reference_yaw_delta_wrapped_rmse_deg": 12.0},
        figures={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert decision["status"] == "yaw_convention_fixed_foundation_ready"
    assert decision["secondary_recommendation"] == "N8B_smoothness_weight_review"
    assert decision["output_only_yaw_correction"] is False
