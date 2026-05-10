"""中文说明：测试 N4H4E1 visual report 的 claim 边界和下一阶段决策。"""

from legsa_gins.visualization.legsa_v23_port_visual_e1_report import make_visual_e1_report


def test_visual_e1_report_recommends_n5_only_when_std_and_plots_fixed():
    report = make_visual_e1_report(
        std_unit_report={"attitude_3sigma_unit_consistency_ok": True},
        plot_report={
            "vector_xy_line_removed": True,
            "vector_cloud_scatter_created": True,
            "up_diff_initial_step_checked": True,
            "required_corrected_figures_generated": True,
            "pure_single_comparison_absent": True,
        },
    )
    assert report["visual_candidate_status"] == "passed_after_std_unit_fix"
    assert report["recommended_next_stage"] == "N5_raw_doppler_factor_foundation"
    assert report["manual_visual_review_required"] is True
    assert report["paper_performance_claim"] is False
    assert report["no_outperform_final_v23_claim"] is True


def test_visual_e1_report_blocks_n5_when_std_unit_not_ok():
    report = make_visual_e1_report(
        std_unit_report={"attitude_3sigma_unit_consistency_ok": False},
        plot_report={
            "vector_xy_line_removed": True,
            "vector_cloud_scatter_created": True,
            "up_diff_initial_step_checked": True,
            "required_corrected_figures_generated": True,
            "pure_single_comparison_absent": True,
        },
    )
    assert report["visual_candidate_status"] == "failed_std_unit_issue"
    assert report["recommended_next_stage"] == "N4H4E1_followup_visual_or_std_fix"
    assert report["paper_performance_claim"] is False
