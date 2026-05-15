"""Unit tests for N8J final decision.

中文说明：final validation 通过时只给 BY2 工程验证 ready，不做论文性能宣称。
"""

from legsa_gins.fgo_feedback.fgo_feedback_final_decision import build_final_decision_report


def test_final_decision_passes_ready_status():
    report = build_final_decision_report(
        selected_policy={"policy_name": "n8i_selected_conservative_feedback", "n8i_selected_policy_match": True, "hidden_policy_change": False, "gate_policy": "combined_conservative_gate", "covariance_policy": "inflation_auto_from_residual_proxy", "window_duration_s": 5.0, "stride_s": 1.0},
        final_manifest={"runtime_outputs_generated": True, "accepted": 4, "output_substitution": False, "direct_nav_override": False},
        sanity_report={"all_checks_passed": True, "checks": {"no_gross_degradation": True}},
        comparison_report={"selected_gross_degradation": False},
    )
    assert report["status"] == "feedback_joint_filter_ready_for_BY2_packaging"
    assert report["paper_performance_claim"] is False
    assert report["outperform_final_v23_claim"] is False
