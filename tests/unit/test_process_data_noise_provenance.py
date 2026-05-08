"""中文说明：测试 process_data/run_final_mainline provenance 只读解析。"""

from pathlib import Path

from legsa_gins.source_audit.process_data_noise_provenance import (
    audit_process_data_script,
    audit_run_final_mainline,
)


def test_process_data_noise_and_run_final_degradation_detected(tmp_path):
    process_data = tmp_path / "process_data.py"
    process_data.write_text(
        "\n".join(
            [
                "BASE_TIME = 1.0",
                "USE_STATUS_YAW = True",
                "YAW_SOURCE_MODE = 'status'",
                "YAW_SIGN = 1.0",
                "YAW_INSTALL_OFFSET_DEG = 0.0",
                "AUTO_APPLY_BEST_INSTALL = False",
                "YAW_NOISE_STD_DEG = 1.5",
                "OUTLIER_RATIO_DEFAULT = 0.15",
                "OUTLIER_MODE_DEFAULT = 'legacy15'",
                "OUTAGE_DURATION_SEC = 10.0",
                "STATUS_YAW_STD_MODE_DEFAULT = 'fixed_1p5'",
                "STATUS_FIXED_YAW_STD_DEG_DEFAULT = 1.5",
                "YAW_STD_MODE_DEFAULT = 'fixed_1p5'",
                "def process_gnss(enable_outage: bool = True):",
                "    noise = np.random.normal(loc=0.0, scale=yaw_noise_std_deg, size=len(yaw_ned))",
                "    np.random.uniform(15.0, 25.0)",
                "    yaw_ned = wrap_deg(yaw_ned + noise)",
                "parser.add_argument('--yaw_noise_std_deg')",
                "parser.add_argument('--outlier_ratio')",
                "parser.add_argument('--outlier_mode')",
                "parser.add_argument('--enable_outage')",
                "parser.add_argument('--yaw_std_mode')",
                "parser.add_argument('--yaw_source_mode')",
                "enable_outage = True if args.enable_outage is None else bool(args.enable_outage)",
            ]
        ),
        encoding="utf-8",
    )
    audit = audit_process_data_script(process_data)
    assert audit["process_gnss_adds_gaussian_yaw_noise"]
    assert audit["process_gnss_adds_legacy_outliers"]
    assert audit["process_gnss_can_disable_outlier_outage_noise_via_cli"]

    run_script = tmp_path / "run_final_mainline.py"
    run_script.write_text(
        "CASES = ["
        "{'yaw_noise_std_deg': 1.5, 'outlier_ratio': 0.15, 'enable_outage': False},"
        "{'yaw_noise_std_deg': 5.0, 'outlier_ratio': 0.15, 'enable_outage': True},"
        "{'yaw_noise_std_deg': 8.0, 'outlier_ratio': 0.15, 'enable_outage': True}]"
        "\ncmd=['--yaw_std_mode','--yaw_noise_std_deg','--outlier_ratio','--outlier_mode','--enable_outage']\n",
        encoding="utf-8",
    )
    run_audit = audit_run_final_mainline(run_script)
    assert run_audit["script_role"] == "degradation_batch_or_final_stress_pipeline"
    assert run_audit["cannot_treat_as_nominal_none_clean_source"]
    assert run_audit["run_final_mainline_degradation_batch"]
