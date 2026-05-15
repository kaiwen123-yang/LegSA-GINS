"""Unit tests for N8J final sanity.

中文说明：sanity 汇总 selected policy、runtime 输出和禁止边界。
"""

from legsa_gins.fgo_feedback.fgo_feedback_final_sanity import build_final_sanity_report


def test_final_sanity_passes_complete_toy_reports():
    report = build_final_sanity_report(
        selected_policy={"n8i_selected_policy_match": True, "hidden_policy_change": False},
        variant_summaries={
            "reject_all_sanity_passed": True,
            "variants": [
                {"policy_id": "baseline_no_feedback", "eval_nav_generated": True},
                {"policy_id": "n8j_selected_conservative_feedback", "nav_generated": True, "std_generated": True, "eval_nav_generated": True, "gross_degradation": False},
                {"policy_id": "reject_all_sanity", "eval_nav_generated": True},
            ],
        },
        evaluation_report={
            "feedback_correction_stats": {
                "position_m": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                "velocity_mps": {"p50": 0.1, "p95": 0.2, "max": 0.3},
                "attitude_deg": {"p50": 1.0, "p95": 2.0, "max": 3.0},
                "yaw_abs_deg": {"p50": 0.5, "p95": 1.0, "max": 2.0},
            }
        },
        final_manifest={"feedback_observations": 6, "accepted": 4, "rejected": 2, "position_feedback_enabled": False, "output_substitution": False, "direct_nav_override": False, "no_future_data": True, "runtime_artifacts_committed": False, "paper_performance_claim": False, "runtime_outputs_generated": True},
        figure_manifest={"all_required_figures_nonempty": True},
    )
    assert report["all_checks_passed"] is True
    assert report["trace_solver_input"] is False
