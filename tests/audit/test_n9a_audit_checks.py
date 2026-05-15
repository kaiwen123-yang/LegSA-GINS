from pathlib import Path

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.n9a_audit_checks import run_check


# 中文说明：使用最小运行报告确认 N9A 审计函数不依赖本地绝对路径。


def test_n9a_core_audit_checks_accept_minimal_runtime_reports(tmp_path):
    report_dir = tmp_path / "n9a"
    report_dir.mkdir()
    write_json(report_dir / "N9A_INPUT_DISCOVERY_REPORT.json", {"enough_to_generate_full_plot_audit": True, "found_result_roots": ["old"], "found_existing_figure_count": 1})
    write_json(report_dir / "N9A_BY2_CASE_DISCOVERY_REPORT.json", {"case_count": 1, "discovered_cases": ["A0_source_backed_ekf_baseline"], "missing_required_cases": []})
    write_json(report_dir / "N9A_PLACEHOLDER_AUDIT_REPORT.json", {"placeholder_count": 0, "applicable_placeholder_count": 0, "empty_axis_count": 0})
    write_json(report_dir / "N9A_DUPLICATE_AUDIT_REPORT.json", {"blocking_duplicate_count": 0, "same_variant_cross_category_duplicate_count": 0})
    write_json(report_dir / "N9A_SEMANTIC_FILENAME_AUDIT_REPORT.json", {"semantic_mismatch_count": 0, "compare_figures_are_true_compare": True})
    write_json(report_dir / "N9A_NOT_APPLICABLE_REASON_REPORT.json", {"not_applicable_without_reason_count": 0})
    write_json(report_dir / "N9A_DERIVED_DATA_LABEL_REPORT.json", {"derived_surrogate_unlabeled_count": 0, "paper_performance_claim": False})
    write_json(report_dir / "N9A_FEEDBACK_APPLICABILITY_AUDIT_REPORT.json", {"feedback_applicability_conflict_count": 0, "A0_feedback_applicable": False})
    write_json(report_dir / "N9A_DEGRADATION_META_REPORT.json", {"N9B_degradation_matrix_run": False, "degradation_meta_missing_case_count": 0})
    write_json(report_dir / "N9A_AUDIT_SANITY_REPORT.json", {"audit_sanity_missing_case_count": 0, "no_future_data_check": True, "no_output_substitution_check": True, "path_leak_check": True})
    write_json(report_dir / "N9A_SUMMARY_PANEL_REPORT.json", {"summary_panel_count": 7, "summary_panels_generated": [{"filename": f"p{i}.png", "present": True, "nonempty": True} for i in range(7)]})
    manifest = tmp_path / "ppt.md"
    manifest.write_text("ppt assets\n", encoding="utf-8")
    write_json(report_dir / "N9A_PPT_ASSET_REPORT.json", {"ppt_asset_count": 7, "ppt_asset_manifest": str(manifest), "pptx_generated": False})
    write_json(report_dir / "N9A_DECISION_REPORT.json", {"algorithm_changes": False, "no_algorithm_changes": True, "degradation_matrix_run": False, "N9B_degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})

    for check_name in [
        "input_discovery",
        "case_discovery",
        "no_placeholder_for_applicable_plots",
        "duplicate_plots",
        "semantic_filename_alignment",
        "not_applicable_reasons",
        "feedback_applicability",
        "no_empty_axes",
        "derived_data_labels",
        "degradation_meta",
        "audit_sanity",
        "summary_panels",
        "ppt_assets",
        "no_degradation_matrix_run",
    ]:
        run_check(check_name, report_dir)
