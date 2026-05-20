import re
from pathlib import Path

from legsa_gins.reporting.by2_n9b1d1_solver_interface_mapping_fix import (
    STAGE,
    default_n9b1d1_runtime_root,
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
            "help_returncode": 2,
            "help_output": (
                "Usage: legsa_gins (--dry-run | --dry-filter-demo | --run-filter-csv) "
                "[--output-dir PATH] [--imu-csv PATH --receiver-csv PATH --max-epochs N "
                "--imu-propagation-mode MODE --heading-offset-mode MODE]"
            ),
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
            "algorithm": "source_backed_EKF",
            "mapping_status": "mapped",
            "command_type": "wsl_command",
            "entrypoint": "/runner/LegSA-GINS/build/cpp/legsa_gins",
            "command": "/runner/LegSA-GINS/build/cpp/legsa_gins --config old.yaml --output-dir old",
            "run_allowed_in_N9B1D": True,
        },
        {
            "case_id": "M_normal_baseline_repeat",
            "pilot_case_id": "nominal_clean_rerun",
            "family_code": "M",
            "algorithm": "Raw_Doppler_EKF",
            "mapping_status": "mapped",
            "command_type": "wsl_command",
            "entrypoint": "/runner/LegSA-GINS/build/cpp/legsa_gins",
            "command": "/runner/LegSA-GINS/build/cpp/legsa_gins --config old.yaml --output-dir old",
            "run_allowed_in_N9B1D": True,
        },
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
    ]


def _write_source_config(workspace_root: Path) -> None:
    path = (
        workspace_root
        / AUDIT_ROOT_NAME
        / "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING"
        / "algorithm_config_mapping"
        / "M_normal_baseline_repeat"
        / "single_antenna_gnss1_status_KF_GINS"
        / "config.yaml"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('imupath: "input.imu"\ngnsspath: "input.gnss"\noutputpath: "legacy"\n', encoding="utf-8")


def test_default_runtime_root_uses_n9b1d1_stage(tmp_path):
    root = default_n9b1d1_runtime_root(tmp_path)
    assert root.parts[-2] == AUDIT_ROOT_NAME
    assert root.name == STAGE


def test_n9b1d1_maps_only_real_compatible_runner_and_blocks_legsa_variants(tmp_path):
    _write_source_config(tmp_path)
    runtime_root = tmp_path / "runtime" / STAGE
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
    repaired = result["command_mapping_matrix_repaired"]
    mapped = [row for row in repaired if row["mapping_status"] == "mapped"]
    assert len(mapped) == 1
    assert mapped[0]["algorithm"] == "single_antenna_gnss1_status_KF_GINS"
    assert mapped[0]["entrypoint"].endswith("/bin/KF-GINS")
    assert "N9B1D_PILOT_SOLVER_EXECUTION_AND_EVALUATION" in mapped[0]["output_root"]
    assert not any(
        row["entrypoint"].endswith("build/cpp/legsa_gins") and " --config " in f" {row['command']} "
        for row in repaired
        if row["run_allowed_in_N9B1D"] is True
    )
    raw = next(row for row in repaired if row["algorithm"] == "Raw_Doppler_EKF")
    assert raw["mapping_status"] == "blocked_requires_real_runner"
    assert "current legsa_gins CLI does not expose option for Raw Doppler" in raw["blocked_reason"]
    source_backed = next(row for row in repaired if row["algorithm"] == "source_backed_EKF")
    assert "diagnostic filter-core only" in source_backed["blocked_reason"]
    assert result["decision_report"]["ready_for_N9B1D_solver_execution"] is True
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))


def test_n9b1d1_tracked_files_do_not_embed_local_absolute_paths():
    root = Path(__file__).resolve().parents[2]
    tracked = [
        root / "src" / "legsa_gins" / "reporting" / "by2_n9b1d1_solver_interface_mapping_fix.py",
        root / "scripts" / "experiments" / "run_n9b1d1_solver_interface_mapping_fix.py",
        root / "scripts" / "audit_n9b1d1_solver_interface_mapping_fix.py",
        Path(__file__),
    ]
    forbidden_patterns = [
        re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+"),
        re.compile("/" + "mnt" + r"/[A-Za-z]/Users/"),
        re.compile("/" + "home" + r"/[^/\s\"']+"),
    ]
    for path in tracked:
        text = path.read_text(encoding="utf-8")
        assert not any(pattern.search(text) for pattern in forbidden_patterns)
