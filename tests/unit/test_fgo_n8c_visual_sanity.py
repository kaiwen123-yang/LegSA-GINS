"""中文说明：测试 N8C visual sanity 汇总。"""

from legsa_gins.fgo.fgo_n8c_visual_sanity import build_n8c_visual_sanity_report


def test_n8c_visual_sanity_passes_basic_boundaries() -> None:
    rows = [{"time": 0.0, "yaw_deg": 1.0}, {"time": 300.0, "yaw_deg": 2.0}]
    report = build_n8c_visual_sanity_report(
        manifest={"no_feedback": True, "output_substitution": False, "candidate_factors_diagnostic_only": True},
        ekf_rows=rows,
        rows_by_variant={"weak_yaw_smoothness": rows},
        ablation_summary={"variants": [{"variant": "weak_yaw_smoothness", "yaw_delta_wrapped_rmse_deg": 0.5, "smoothness_factor_deleted_for_metric": False}]},
        plot_coverage={"visual_validation_passed": True},
        factor_contribution={"review_complete": True},
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert report["visual_sanity_passed"]
    assert not report["paper_performance_claim"]
