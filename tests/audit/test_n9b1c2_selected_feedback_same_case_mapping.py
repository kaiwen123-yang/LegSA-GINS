from pathlib import Path

from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1c2_selected_feedback_same_case_mapping,
    validate_n9b1c2_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1c2_audit_contract(tmp_path):
    runtime_root = tmp_path / "n9b1c2"
    result = run_n9b1c2_selected_feedback_same_case_mapping(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
    )
    validation = validate_n9b1c2_result(
        ROOT,
        runtime_root,
        result["selected_feedback_mapping_matrix"],
        result["repaired_command_plan_matrix"],
        result["wsl_dryrun_command_matrix"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
    assert all(row["solver_run"] is False for row in result["selected_feedback_mapping_matrix"])
    assert all(row["official_evaluator_run"] is False for row in result["selected_feedback_mapping_matrix"])
    assert all(row["ready_for_N9B2_execution"] is False for row in result["selected_feedback_mapping_matrix"])
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))
