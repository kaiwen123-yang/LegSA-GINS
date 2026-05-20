from pathlib import Path

from legsa_gins.reporting.by2_real_pilot_input_generator import SourcePaths
from legsa_gins.reporting.by2_real_solver_entrypoint_config_mapping import (
    KF_GINS_BASELINE_ENTRYPOINT,
    LEGSA_ENTRYPOINT,
    RuntimeDependencyPaths,
    default_n9b1c_runtime_root,
    run_real_solver_entrypoint_config_mapping,
    validate_n9b1c_result,
)


ROOT = Path(__file__).resolve().parents[2]


def _deps(tmp_path: Path) -> RuntimeDependencyPaths:
    imu = tmp_path / "test1.imu"
    go2 = tmp_path / "by2.txt"
    raw = tmp_path / "gnss1-raw.csv"
    feedback = tmp_path / "FGO_FEEDBACK_OBSERVATIONS.csv"
    for path in [imu, go2, raw, feedback]:
        path.write_text("placeholder dependency for static mapping test\n", encoding="utf-8")
    return RuntimeDependencyPaths(imu=imu, go2=go2, raw_doppler=raw, feedback_observations=feedback, source="unit_test")


def test_default_runtime_root_uses_n9b1c_stage():
    root = default_n9b1c_runtime_root(ROOT)
    assert root.parts[-2] == "by2\u6570\u636e\u96c6\u7ed8\u56fe\u5ba1\u8ba1"
    assert root.name == "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING"


def test_n9b1c_maps_real_entrypoints_and_blocks_reference_algorithms(tmp_path):
    runtime_root = tmp_path / "n9b1c"
    result = run_real_solver_entrypoint_config_mapping(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        source_paths=SourcePaths(None, None, tmp_path / "test1.imu", "unit_test"),
        dependency_paths=_deps(tmp_path),
    )
    validation = validate_n9b1c_result(
        runtime_root,
        result["command_mapping_matrix"],
        result["algorithm_ready_matrix"],
        result["blocked_mapping_matrix"],
        result["wsl_dryrun_command_matrix"],
        True,
    )
    assert validation["status"] == "pass"
    commands = [row["command"] for row in result["command_mapping_matrix"]]
    assert not any("python -m legsa_gins.future_solver_entry" in command for command in commands)
    mapped = [row for row in result["command_mapping_matrix"] if row["mapping_status"] == "mapped"]
    assert any(row["algorithm"] == "single_antenna_gnss1_status_KF_GINS" and row["entrypoint"] == KF_GINS_BASELINE_ENTRYPOINT for row in mapped)
    assert any(row["algorithm"] == "source_backed_EKF" and row["entrypoint"] == LEGSA_ENTRYPOINT for row in mapped)
    assert all("N9B1D_PILOT_SOLVER_EXECUTION" in row["future_output_root"] for row in mapped)
    assert all("N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING" not in row["future_output_root"] for row in mapped)
    assert any(row["algorithm"] == "final_v23_dual_antenna_EKF" and row["mapping_status"] == "fixed_reference" for row in result["command_mapping_matrix"])
    assert any(row["algorithm"] == "true_no_feedback_FGO" and row["mapping_status"] == "diagnostic_blocked" for row in result["command_mapping_matrix"])
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))


def test_n9b1c_tracked_files_do_not_embed_windows_absolute_paths():
    tracked = [
        ROOT / "src" / "legsa_gins" / "reporting" / "by2_real_solver_entrypoint_config_mapping.py",
        ROOT / "scripts" / "experiments" / "run_n9b1c_real_solver_entrypoint_config_mapping.py",
        ROOT / "scripts" / "audit_n9b1c_real_solver_entrypoint_config_mapping.py",
        Path(__file__),
    ]
    windows_prefix = "C:" + "\\Users\\"
    posix_prefix = "C:" + "/Users/"
    for path in tracked:
        text = path.read_text(encoding="utf-8")
        assert windows_prefix not in text
        assert posix_prefix not in text
