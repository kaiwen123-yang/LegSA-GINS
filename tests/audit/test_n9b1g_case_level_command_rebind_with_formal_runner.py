from pathlib import Path

from legsa_gins.reporting.by2_n9b1g_case_level_command_rebind_with_formal_runner import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1g_case_level_command_rebind_with_formal_runner,
    validate_n9b1g_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1g_audit_contract(tmp_path):
    runtime_root = tmp_path / "n9b1g"
    result = run_n9b1g_case_level_command_rebind_with_formal_runner(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
    )
    validation = validate_n9b1g_result(
        ROOT,
        runtime_root,
        result["n9b1d_case_level_command_matrix"],
        result["wsl_dryrun_case_level_commands"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
    rows = result["n9b1d_case_level_command_matrix"]
    assert all(row["solver_run"] is False for row in rows)
    assert all(row["official_evaluator_run"] is False for row in rows)
    assert all(row["trace_solver_input"] is False for row in rows)
    assert all(row["final_v23_solver_input"] is False for row in rows)
    assert all(row["ready_for_N9B2_execution"] is False for row in rows)
    assert not list(runtime_root.rglob("RUN_MANIFEST.json"))
    assert not list(runtime_root.rglob("EVAL_NAV.csv"))
    assert not list(runtime_root.rglob("*.nav"))
    assert not list(runtime_root.rglob("*.png"))
