from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.n9a_r1_audit_checks import run_check


# 中文说明：使用最小 N9A_R1 报告验证审计函数能拦住 case/source 边界回退。


def test_n9a_r1_core_audit_checks_accept_minimal_reports(tmp_path):
    report_dir = tmp_path / "n9a_r1"
    report_dir.mkdir()

    write_json(
        report_dir / "N9A_R1_SOURCE_LINEAGE_REPORT.json",
        {
            "source_lineage": {
                "dual_antenna_gnss_raw": ["<GNSS1_RAW>", "<GNSS2_RAW>"],
                "dual_antenna_gnss_status": ["<GNSS1_STATUS>", "<GNSS2_STATUS>"],
                "truth_reference_evaluation_only": "<TRACE_TRUTH>",
                "fused_body_imu_highlevel": "<GO2_BODY_IMU_HIGHLEVEL>",
                "receiver_imu_diagnostic_only": ["<FIXPOSITION_IMU_DATA>"],
            },
            "initial_n9a_status": "N9A_initial_audit_scope_mismatch",
            "initial_n9a_ready_for_N9B": False,
        },
    )
    write_json(
        report_dir / "N9A_R1_INPUT_FILE_AUDIT_REPORT.json",
        {
            "all_required_source_files_exist": True,
            "raw_status_time_audit_passed": True,
            "files": {
                key: {"exists": True, "row_count": 1}
                for key in ["gnss1_raw", "gnss2_raw", "gnss1_status", "gnss2_status", "trace_truth", "go2_body_imu_highlevel"]
            },
        },
    )
    write_json(
        report_dir / "N9A_R1_CASE_MODEL_REPORT.json",
        {
            "main_case": "BY2_normal_clean",
            "case_count": 1,
            "algorithm_series_are_comparison_series_not_cases": True,
            "ablation_variants_counted_as_normal_cases": False,
            "n8k_ablation_archive_variant_count": 30,
        },
    )
    write_json(
        report_dir / "N9A_R1_BY2_NORMAL_PLOT_AUDIT_REPORT.json",
        {"placeholder_count": 0, "inventory": [{"applicable": True, "placeholder": False}]},
    )
    write_json(
        report_dir / "N9A_R1_CATEGORY_COVERAGE_REPORT.json",
        {"case_name": "BY2_normal_clean", "category_count": 14, "category_coverage_complete": True, "missing_count": 0},
    )
    write_json(
        report_dir / "N9A_R1_TRUTH_REFERENCE_USAGE_REPORT.json",
        {"trace_truth_exists": True, "trace_solver_input": False, "trace_usage": "truth_reference_evaluation_only"},
    )
    write_json(
        report_dir / "N9A_R1_BODY_IMU_SOURCE_REPORT.json",
        {
            "go2_body_imu_highlevel_exists": True,
            "by2_txt_is_fused_body_imu_highlevel": True,
            "go2_position_truth": False,
            "go2_yaw_truth": False,
            "go2_contact_truth": False,
        },
    )
    write_json(
        report_dir / "N9A_R1_RECEIVER_IMU_DIAGNOSTIC_REPORT.json",
        {"receiver_imu_diagnostic_only": True, "receiver_imu_used_as_fused_body_imu": False},
    )
    write_json(
        report_dir / "N9A_R1_DECISION_REPORT.json",
        {
            "algorithm_changes": False,
            "no_algorithm_changes": True,
            "degradation_matrix_run": False,
            "N9B_degradation_matrix_run": False,
            "paper_performance_claim": False,
            "outperform_final_v23_claim": False,
            "rtk_fixed_claim": False,
            "raw_dual_antenna_heading_claim": False,
            "tight_coupling_claim": False,
            "full_raw_gnss_factor_claim": False,
            "full_pose_fgo_claim": False,
        },
    )

    for check_name in [
        "source_lineage",
        "input_files_exist",
        "case_model",
        "trace_evaluation_only",
        "body_imu_source",
        "receiver_imu_diagnostic_only",
        "no_ablation_variants_as_cases",
        "normal_plot_coverage",
        "no_placeholder_for_applicable_plots",
        "no_degradation_matrix_run",
    ]:
        run_check(check_name, report_dir)
