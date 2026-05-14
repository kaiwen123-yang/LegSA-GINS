"""中文说明：测试 N8C decision 规则。"""

from legsa_gins.fgo.fgo_n8c_decision import make_n8c_decision


def test_n8c_decision_routes_suspicious_factor_to_review() -> None:
    decision = make_n8c_decision(
        plot_coverage={"all_mandatory_figures_present": True, "all_mandatory_figures_nonempty": True},
        visual_sanity={"visual_sanity_passed": True, "yaw_delta_reasonable_after_n8a2": True},
        factor_contribution={"suspicious_no_effect_factors": ["RawDopplerVelocityFactor"], "influential_factors": ["SmoothnessFactor"]},
        candidate_review={"candidate_factor_reviews": [{"status": "candidate_needs_data_review"}]},
    )
    assert decision["status"] == "factor_contribution_needs_review"
    assert decision["recommended_next_stage"] == "N8C2_factor_activation_review"
    assert not decision["paper_performance_claim"]
