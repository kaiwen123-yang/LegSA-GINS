"""Tests for N8C3 Raw Doppler decision.

中文说明：验证 solver residual 注入成功后进入 N8D 建议但不执行 N8D。
"""

from legsa_gins.fgo.fgo_n8c3_decision import make_n8c3_decision


def test_n8c3_decision_reports_fixed_or_dominated_after_successful_injection() -> None:
    decision = make_n8c3_decision(
        dataset_link_report={"source_found": True, "aligned_factor_count": 10},
        solver_injection_report={"appears_in_solver_residual_vector": True, "dim_delta": 30, "residual_row_count": 30, "jacobian_nonzero_count": 30},
        toggle_regression_report={"toggle_regression_passed": True},
        variant_report={
            "variants": [
                {"variant": "weak_yaw_smoothness_with_raw_fixed", "yaw_delta_wrapped_rmse_deg": 0.1, "gross_degradation": False, "raw_doppler_enabled": True},
                {"variant": "raw_doppler_off_verified", "yaw_delta_wrapped_rmse_deg": 0.1, "gross_degradation": False, "raw_doppler_enabled": False},
            ]
        },
        figure_manifest={"figure_count_total": 10, "required_figures_nonempty": True},
    )
    assert decision["status"] == "raw_doppler_active_consistent_or_dominated"
    assert decision["recommended_next_stage"] == "N8D_factor_weight_policy_review"
    assert not decision["paper_performance_claim"]
