from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.n9a_r2_audit_checks import run_check
from legsa_gins.reporting.n9a_r2_by2_normal_real_plot_materialization import TARGET_ALGORITHM_SERIES


# 中文说明：审计测试覆盖缺失输出、禁止越界和不误判完成的合同。
def test_n9a_r2_core_audit_checks_accept_missing_outputs_failure(tmp_path):
    report_dir = tmp_path / "n9a_r2"
    report_dir.mkdir()
    series = [
        {
            "series_name": name,
            "available": False,
            "output_root": "",
            "nav_path": "",
            "std_path": "",
            "eval_path": "",
            "manifest_path": "",
            "metrics_path": "",
            "figure_source_role": "missing_real_algorithm_output",
            "row_count_nav": 0,
            "row_count_eval": 0,
            "row_count_std": 0,
            "can_plot_trajectory": False,
            "can_plot_position_error": False,
            "can_plot_velocity": False,
            "can_plot_attitude": False,
            "can_plot_consistency": False,
            "can_plot_compare": False,
            "missing_reason": "missing",
        }
        for name in TARGET_ALGORITHM_SERIES
    ]
    write_json(
        report_dir / "N9A_R2_ALGORITHM_OUTPUT_DISCOVERY_REPORT.json",
        {
            "algorithm_series_count": len(TARGET_ALGORITHM_SERIES),
            "available_algorithm_series_count": 0,
            "algorithm_series": series,
            "formal_ablation_variants_counted_as_normal_cases": False,
        },
    )
    write_json(report_dir / "N9A_R2_SOURCE_PROXY_EXCLUSION_REPORT.json", {"source_data_treated_as_algorithm_estimate": False, "trace_solver_input": False, "by2_txt_truth": False})
    write_json(report_dir / "N9A_R2_REAL_TRAJECTORY_SEMANTICS_REPORT.json", {"trajectory_category_complete": False})
    write_json(report_dir / "N9A_R2_REAL_POSITION_ERROR_SEMANTICS_REPORT.json", {"position_error_category_complete": False, "gnss_status_minus_trace_as_algorithm_error": False})
    write_json(report_dir / "N9A_R2_METRIC_BAR_SEMANTICS_REPORT.json", {"non_bar_metric_bar_count": 0, "bar_entries": []})
    write_json(report_dir / "N9A_R2_VELOCITY_SOURCE_DISTINCTION_REPORT.json", {"same_proxy_used_for_all_velocity_sources": False})
    write_json(report_dir / "N9A_R2_COMPARE_REQUIRES_ALGORITHM_OUTPUTS_REPORT.json", {"available_algorithm_series_count": 0, "compare_complete": False})
    write_json(report_dir / "N9A_R2_CONSISTENCY_REQUIRES_STD_REPORT.json", {"error_proxy_used_as_3sigma": False, "consistency_entries_present_without_std": 0})
    write_json(report_dir / "N9A_R2_BY2_NORMAL_REAL_PLOT_AUDIT_REPORT.json", {"inventory": [], "placeholder_count": 0, "missing_count": 1})
    write_json(report_dir / "N9A_R2_CATEGORY_COVERAGE_REPORT.json", {"category_coverage_complete": False})
    write_json(
        report_dir / "N9A_R2_DECISION_REPORT.json",
        {
            "status": "N9A_R2_algorithm_outputs_missing",
            "ready_for_N9B": False,
            "algorithm_changes": False,
            "no_algorithm_changes": True,
            "degradation_matrix_run": False,
            "N9B_degradation_matrix_run": False,
            "paper_performance_claim": False,
            "outperform_final_v23_claim": False,
        },
    )

    for check_name in [
        "algorithm_output_discovery",
        "no_source_proxy_as_algorithm_result",
        "real_trajectory_semantics",
        "real_position_error_semantics",
        "metric_bar_semantics",
        "velocity_source_distinction",
        "compare_requires_algorithm_outputs",
        "consistency_requires_std",
        "no_false_complete",
        "no_placeholder_for_applicable_plots",
        "no_degradation_matrix_run",
    ]:
        run_check(check_name, report_dir)
