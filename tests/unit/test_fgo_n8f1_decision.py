"""Unit tests for N8F1 decision.

中文说明：检查 N8F1 pass 只给 merge/tag 前图像验证建议，不进入 N8G 实现。
"""

from legsa_gins.fgo.fgo_n8f1_decision import build_n8f1_decision_report


def test_n8f1_decision_passes_after_visual_checks() -> None:
    report = build_n8f1_decision_report(
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True, "figure_count_total": 23},
        coverage_report={"visual_validation_passed": True},
        signal_report={"all_new_factors_have_real_signal": True, "candidate_stack": {"gross_degradation_flag": False}},
        semantic_report={"semantic_guard_passed": True},
        sanity_report={"visual_sanity_passed": True},
    )
    assert report["status"] == "legged_candidate_factor_visual_validation_passed"
    assert report["no_feedback"] is True
    assert report["paper_performance_claim"] is False

