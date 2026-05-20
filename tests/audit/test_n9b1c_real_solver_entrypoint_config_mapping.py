from pathlib import Path

from legsa_gins.reporting.by2_real_solver_entrypoint_config_mapping import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_real_solver_entrypoint_config_mapping,
    validate_n9b1c_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1c_audit_contract(tmp_path):
    runtime_root = tmp_path / "n9b1c"
    result = run_real_solver_entrypoint_config_mapping(ROOT, runtime_root=runtime_root, write_outputs=True)
    validation = validate_n9b1c_result(
        runtime_root,
        result["command_mapping_matrix"],
        result["algorithm_ready_matrix"],
        result["blocked_mapping_matrix"],
        result["wsl_dryrun_command_matrix"],
        True,
    )
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
    assert all(row["solver_run"] is False for row in result["command_mapping_matrix"])
    assert all(row["official_evaluator_run"] is False for row in result["command_mapping_matrix"])
    assert all(row["ready_for_N9B2_execution"] is False for row in result["command_mapping_matrix"])
    assert all(row["dry_run_only"] is True and row["executed"] is False for row in result["wsl_dryrun_command_matrix"])
