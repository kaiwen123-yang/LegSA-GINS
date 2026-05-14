"""中文说明：测试 N8B decision boundary。"""

from legsa_gins.fgo.fgo_n8b_decision import make_n8b_decision


def test_n8b_decision_prefers_weak_policy_when_ready() -> None:
    decision = make_n8b_decision(
        ablation_summary={"variants": [{"solve_status": "solved", "finite_output": True}]},
        smoothness_review={"weak_yaw_smoothness_improves_without_degradation": True, "recommended_policy": "weak_yaw_smoothness_policy"},
        factor_weight_review={"suspect_factors": ["SmoothnessFactor"]},
        candidate_review={"candidate_factor_reviews": [{"status": "candidate_not_ready"}]},
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert decision["status"] == "weak_yaw_smoothness_policy_ready"
    assert decision["recommended_next_stage"] == "N8C_no_feedback_fgo_visual_validation"
    assert not decision["paper_performance_claim"]
