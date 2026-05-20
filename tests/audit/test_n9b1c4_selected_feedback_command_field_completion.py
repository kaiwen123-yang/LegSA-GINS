from pathlib import Path

from legsa_gins.reporting.by2_n9b1c4_selected_feedback_command_field_completion import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1c4_selected_feedback_command_field_completion,
    validate_n9b1c4_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1c4_audit_contract(tmp_path):
    runtime_root = tmp_path / "n9b1c4"
    result = run_n9b1c4_selected_feedback_command_field_completion(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun_refresh=False,
    )
    validation = validate_n9b1c4_result(
        ROOT,
        runtime_root,
        result["n9b1d_ready_command_matrix"],
        result["command_field_completion_diff"],
        result["wsl_dryrun_refresh"],
        result["dependency_graph_cleanup_report"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
    assert all(row["solver_run"] is False for row in result["n9b1d_ready_command_matrix"])
    assert all(row["official_evaluator_run"] is False for row in result["n9b1d_ready_command_matrix"])
    assert all(row["ready_for_N9B2_execution"] is False for row in result["n9b1d_ready_command_matrix"])
    assert all(row["executed"] is False for row in result["wsl_dryrun_refresh"])
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))
