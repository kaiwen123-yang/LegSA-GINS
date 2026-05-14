"""Unit tests for N8F decision policy.

中文说明：检查 N8F decision 只输出工程下一阶段建议。
"""

from legsa_gins.fgo.fgo_n8f_decision import build_n8f_decision_report


def test_decision_promotes_stable_foot_factor_to_n8g_review() -> None:
    report = build_n8f_decision_report(
        contact_report={"rows": 10, "scale_p95": 1.2},
        foot_report={"factor_rows": 4, "toggle_works": True},
        yawrate_report={"factor_rows": 3, "toggle_works": True},
        relative_report={"factor_rows": 3, "toggle_works": True},
        contracts_report={"all_jacobian_checks_passed": True, "all_no_truth_claim": True, "all_trace_input_false": True, "all_finalv23_input_false": True},
        comparison_report={"candidate_solver_injection_failures": [], "gross_degradation_variants": []},
    )
    assert report["status"] == "foot_kinematic_factor_ready_for_N8G_feedback_review"
    assert report["fgo_output_feedback_to_ekf"] is False
    assert report["paper_performance_claim"] is False
