"""Unit tests for N8I covariance refinement.

中文说明：block-wise conservative inflation 可作为稳定候选，但不能声明 R shrink。
"""

from types import SimpleNamespace

from legsa_gins.fgo_feedback.fgo_feedback_covariance_refinement import build_covariance_refinement_report


def test_covariance_refinement_selects_blockwise_candidate_when_stable():
    bundle = SimpleNamespace(
        policy_summaries={
            "cov_auto_residual_proxy": {"feedback_accept_count": 6, "feedback_reject_count": 0, "eval_nav_generated": True},
            "cov_velocity_x2_attitude_x4": {"feedback_accept_count": 6, "feedback_reject_count": 0, "eval_nav_generated": True},
        },
        covariance_reports={
            "cov_auto_residual_proxy": {"std_att_stats": {"p95": 3.0}, "no_R_shrink": True},
            "cov_velocity_x2_attitude_x4": {"std_att_stats": {"p95": 6.0}, "block_scales": {"v": 2.0, "att": 4.0}, "no_R_shrink": True},
        },
        evaluation_by_policy={
            "cov_auto_residual_proxy": {"clean_gross_degradation": False},
            "cov_velocity_x2_attitude_x4": {"clean_gross_degradation": False},
        },
        trace_rows={
            "cov_auto_residual_proxy": [{"attitude_norm_deg": 4.5, "accepted": 1}],
            "cov_velocity_x2_attitude_x4": [{"attitude_norm_deg": 3.0, "accepted": 1}],
        },
        n8g_reports={"FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json": {"conservative_inflation_factor": 2.1543}},
    )
    report = build_covariance_refinement_report(bundle)
    assert report["selected_covariance_policy"] == "block_velocity_x2_attitude_x4"
    assert report["no_R_shrink_claim"] is True
    assert report["final_v23_output_solver_input"] is False
