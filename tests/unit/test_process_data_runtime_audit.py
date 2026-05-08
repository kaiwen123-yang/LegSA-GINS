"""中文说明：process_data runtime 参数审计测试只解析 toy 源码。"""

from pathlib import Path

from legsa_gins.source_audit.process_data_runtime_audit import (
    extract_process_data_defaults,
    make_process_data_runtime_parameter_report,
    search_run_invocations,
)


def test_defaults_parser_extracts_yaw_params(tmp_path: Path):
    process_data = tmp_path / "process_data.py"
    process_data.write_text(
        "\n".join(
            [
                "BASE_TIME = 1772784000.0",
                "USE_STATUS_YAW = True",
                "YAW_SIGN = -1.0",
                "YAW_INSTALL_OFFSET_DEG = 90.0",
                "AUTO_APPLY_BEST_INSTALL = False",
                "YAW_SOURCE_MODE = 'status'",
                "YAW_NOISE_STD_DEG = 0.0",
                "OUTAGE_DURATION_SEC = 0.0",
                "OUTLIER_RATIO_DEFAULT = 0.0",
                "OUTLIER_MODE_DEFAULT = 'none'",
                "STATUS_YAW_STD_MODE_DEFAULT = 'fixed_1p5'",
                "STATUS_FIXED_YAW_STD_DEG_DEFAULT = 1.5",
                "YAW_STD_MODE_DEFAULT = 'fixed_1p5'",
                "IMU_INSTALL_ROLL_DEG_DEFAULT = -1.0",
                "IMU_INSTALL_PITCH_DEG_DEFAULT = 0.0",
                "IMU_INSTALL_YAW_DEG_DEFAULT = 0.0",
                "IMU_GNSS_TIME_OFFSET_SEC_DEFAULT = 0.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = extract_process_data_defaults(process_data)
    assert report["defaults"]["BASE_TIME"] == 1772784000.0
    assert report["defaults"]["YAW_SIGN"] == -1.0
    assert report["defaults"]["YAW_INSTALL_OFFSET_DEG"] == 90.0


def test_invocation_search_finds_explicit_safe_flags(tmp_path: Path):
    run_script = tmp_path / "run_final_v23.py"
    run_script.write_text(
        "python3 process_data.py --generate_both_gnss --yaw_source_mode status "
        "--status_yaw_std_mode fixed_1p5 --outlier_mode none --yaw_noise_std_deg 0\n",
        encoding="utf-8",
    )
    invocations = search_run_invocations(tmp_path)
    defaults = {"defaults": {"YAW_SOURCE_MODE": "status", "OUTLIER_MODE_DEFAULT": "none", "YAW_NOISE_STD_DEG": 0.0}}
    report = make_process_data_runtime_parameter_report(defaults, invocations)
    assert invocations["explicit_safe_flags_found"] is True
    assert report["explicit_nominal_safe_flags_found"] is True
