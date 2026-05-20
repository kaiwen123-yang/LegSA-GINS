from pathlib import Path

from legsa_gins.reporting.by2_n9b1d1_solver_interface_mapping_fix import (
    STAGE,
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1d1_solver_interface_mapping_fix,
    validate_n9b1d1_result,
)
from legsa_gins.reporting.by2_real_pilot_input_generator import AUDIT_ROOT_NAME


def _interface_probe() -> dict:
    return {
        "legsa": {
            "runner_id": "legsa_cpp_binary",
            "path": "/runner/LegSA-GINS/build/cpp/legsa_gins",
            "working_directory": "/runner/LegSA-GINS",
            "exists": True,
            "help_output": "Usage: legsa_gins (--dry-run | --dry-filter-demo | --run-filter-csv) [--output-dir PATH] [--imu-csv PATH --receiver-csv PATH]",
            "supports_config": False,
            "supports_run_filter_csv": True,
        },
        "kf_gins": {
            "runner_id": "kf_gins_baseline_binary",
            "path": "/runner/KF-GINS-Baseline/bin/KF-GINS",
            "working_directory": "/runner/KF-GINS-Baseline",
            "exists": True,
            "supports_positional_config": True,
        },
    }


def _source_rows() -> list[dict]:
    return [
        {
            "case_id": "M_normal_baseline_repeat",
            "pilot_case_id": "nominal_clean_rerun",
            "family_code": "M",
            "algorithm": "single_antenna_gnss1_status_KF_GINS",
            "mapping_status": "mapped",
            "command_type": "external_kf_gins",
            "entrypoint": "/runner/KF-GINS-Baseline/bin/KF-GINS",
            "generated_config_path": "algorithm_config_mapping/M_normal_baseline_repeat/single_antenna_gnss1_status_KF_GINS/config.yaml",
            "run_allowed_in_N9B1D": True,
        },
        {
            "case_id": "M_normal_baseline_repeat",
            "pilot_case_id": "nominal_clean_rerun",
            "family_code": "M",
            "algorithm": "selected_feedback_EKF",
            "mapping_status": "mapped",
            "command_type": "wsl_command",
            "entrypoint": "/runner/LegSA-GINS/build/cpp/legsa_gins",
            "command": "/runner/LegSA-GINS/build/cpp/legsa_gins --config old.yaml --output-dir old",
            "run_allowed_in_N9B1D": True,
        },
    ]


def test_n9b1d1_audit_contract(tmp_path):
    config = (
        tmp_path
        / AUDIT_ROOT_NAME
        / "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING"
        / "algorithm_config_mapping"
        / "M_normal_baseline_repeat"
        / "single_antenna_gnss1_status_KF_GINS"
        / "config.yaml"
    )
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('imupath: "input.imu"\ngnsspath: "input.gnss"\noutputpath: "legacy"\n', encoding="utf-8")
    runtime_root = tmp_path / STAGE
    result = run_n9b1d1_solver_interface_mapping_fix(
        tmp_path,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
        source_rows=_source_rows(),
        interface_probe=_interface_probe(),
    )
    validation = validate_n9b1d1_result(
        tmp_path,
        runtime_root,
        result["runner_interface_inventory"],
        result["command_mapping_matrix_repaired"],
        result["wsl_dryrun_repaired_commands"],
        result["n9b1d_ready_execution_matrix"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
    assert all(row["solver_run"] is False for row in result["command_mapping_matrix_repaired"])
    assert all(row["official_evaluator_run"] is False for row in result["command_mapping_matrix_repaired"])
    assert all(row["ready_for_N9B2_execution"] is False for row in result["command_mapping_matrix_repaired"])
    selected = next(row for row in result["command_mapping_matrix_repaired"] if row["algorithm"] == "selected_feedback_EKF")
    assert selected["mapping_status"] == "blocked_requires_real_runner"
    assert "FGO feedback/selected feedback" in selected["blocked_reason"]
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))
