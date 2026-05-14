"""Unit tests for N8F1 visual sanity.

中文说明：检查图像 sanity 汇总保留 no-feedback 和 no-claim 边界。
"""

from legsa_gins.fgo.fgo_n8f_visual_sanity import build_n8f_visual_sanity_report


def test_visual_sanity_passes_clean_reports() -> None:
    report = build_n8f_visual_sanity_report(
        visual_manifest={"no_feedback": True, "output_substitution": False, "trace_solver_input": False, "final_v23_solver_input": False, "go2_truth_claim": False},
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True},
        coverage_report={"visual_validation_passed": True},
        signal_report={
            "contact_aware_weighting": {"signal_status": "informative"},
            "foot_kinematic_velocity": {"signal_status": "informative"},
            "yawrate_between": {"signal_status": "informative"},
            "relative_odometry_between": {"signal_status": "informative"},
            "candidate_stack": {"gross_degradation_flag": False},
        },
        semantic_report={"semantic_guard_passed": True},
        n8f_decision={"no_feedback": True, "output_substitution": False, "go2_truth_claim": False},
    )
    assert report["visual_sanity_passed"] is True
    assert report["paper_performance_claim"] is False

