"""中文说明：测试 N4H4E visual report 不写性能 claim 并保留人工复核边界。"""

from legsa_gins.visualization.legsa_v23_port_visual_report import make_visual_validation_report


def test_visual_report_keeps_no_performance_claim_and_recommends_n5_only_when_passed():
    report = make_visual_validation_report(
        sanity={
            "visual_candidate_passed": True,
            "required_figures_generated": True,
            "pure_single_comparison_absent": True,
            "blocking_issues": [],
        },
        figure_manifest={"figure_count_total": 41, "figure_count_by_folder": {"01_trajectory": 4}},
        input_manifest={
            "port_nav_found": True,
            "port_std_found": True,
            "final_v23_nav_found": True,
            "final_v23_std_found": True,
            "trace_found": True,
            "r3c_all_reports_found": True,
        },
    )

    assert report["recommended_next_stage"] == "N5_raw_doppler_factor_foundation"
    assert report["paper_performance_claim"] is False
    assert report["proposed_factor_claim"] is False
    assert report["no_outperform_final_v23_claim"] is True


def test_visual_report_routes_failed_candidate_to_anomaly_debug():
    report = make_visual_validation_report(
        sanity={
            "visual_candidate_passed": False,
            "required_figures_generated": False,
            "pure_single_comparison_absent": True,
            "blocking_issues": ["required_figures_missing"],
        },
        figure_manifest={"figure_count_total": 12, "figure_count_by_folder": {}},
        input_manifest={},
    )

    assert report["recommended_next_stage"] == "N4H4E_visual_anomaly_debug"
    assert report["paper_performance_claim"] is False
