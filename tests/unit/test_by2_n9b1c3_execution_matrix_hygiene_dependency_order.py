from pathlib import Path

from legsa_gins.reporting.by2_n9b1c3_execution_matrix_hygiene_dependency_order import (
    L_DISABLED_CASE,
    M_CLEAN_REPEAT_CASE,
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1c3_execution_matrix_hygiene_dependency_order,
    validate_n9b1c3_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1c3_locks_ready_matrix_and_selected_feedback_acceptance(tmp_path):
    runtime_root = tmp_path / "n9b1c3"
    result = run_n9b1c3_execution_matrix_hygiene_dependency_order(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_path_preflight=False,
        run_wsl_dryrun_refresh=False,
    )
    validation = validate_n9b1c3_result(
        ROOT,
        runtime_root,
        result["n9b1d_ready_command_matrix"],
        result["stale_field_diff"],
        result["case_dependency_graph"],
        result["wsl_path_preflight"],
        result["wsl_dryrun_refresh"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    assert result["decision_report"]["status"] == "N9B1C3_execution_matrix_clean_and_order_locked"
    assert result["decision_report"]["recommended_next_stage"] == "human_review_N9B1C3_then_N9B1D_solver_execution"
    assert result["decision_report"]["ready_for_N9B1D_solver_execution"] is True
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()

    executable = [row for row in result["n9b1d_ready_command_matrix"] if row["n9b1d_executable"] is True]
    assert executable
    assert not [row for row in executable if row.get("block_reason") or row.get("blocked_reason")]
    assert all(row.get("n9b1b_block_reason") in {"superseded_by_N9B1C3", "none"} for row in executable)

    selected = [
        row
        for row in result["n9b1d_ready_command_matrix"]
        if row["algorithm"] == "selected_feedback_EKF" and row.get("mapping_status") == "mapped"
    ]
    assert selected
    assert all(row["selected_feedback_safe_candidate"] is True for row in selected)
    assert all(row["selected_feedback_block_reason"] == "none" for row in selected)
    assert {row["selected_feedback_acceptance"] for row in selected} == {
        "mapped_same_case_plan",
        "mapped_clean_repeat",
        "mapped_disabled_marker",
    }
    assert not [
        row
        for row in selected
        if row["case_id"] not in {M_CLEAN_REPEAT_CASE, L_DISABLED_CASE}
        and row["selected_feedback_acceptance"] != "mapped_same_case_plan"
    ]


def test_n9b1c3_dependency_graph_has_required_selected_feedback_order(tmp_path):
    result = run_n9b1c3_execution_matrix_hygiene_dependency_order(
        ROOT,
        runtime_root=tmp_path / "n9b1c3",
        write_outputs=True,
        run_wsl_path_preflight=False,
        run_wsl_dryrun_refresh=False,
    )
    graph = result["case_dependency_graph"]
    same_case = [row for row in graph if row["dependency_mode"] == "same_case_selected_feedback"]
    assert same_case
    assert all(row["edge_type"] == "baseline_to_feedback_to_selected_feedback" for row in same_case)
    assert {row["order_index"] for row in same_case} == {1, 2}
    assert any(row["case_id"] == M_CLEAN_REPEAT_CASE and row["dependency_mode"] == "clean_repeat_selected_feedback" for row in graph)
    assert any(row["case_id"] == L_DISABLED_CASE and row["dependency_mode"] == "disabled_marker_selected_feedback" for row in graph)


def test_n9b1c3_validation_rejects_stale_executable_blocker(tmp_path):
    result = run_n9b1c3_execution_matrix_hygiene_dependency_order(
        ROOT,
        runtime_root=tmp_path / "n9b1c3",
        write_outputs=True,
        run_wsl_path_preflight=False,
        run_wsl_dryrun_refresh=False,
    )
    rows = [dict(row) for row in result["n9b1d_ready_command_matrix"]]
    target = next(row for row in rows if row["n9b1d_executable"] is True)
    target["block_reason"] = "stale blocker"
    validation = validate_n9b1c3_result(
        ROOT,
        tmp_path / "n9b1c3",
        rows,
        result["stale_field_diff"],
        result["case_dependency_graph"],
        result["wsl_path_preflight"],
        result["wsl_dryrun_refresh"],
        runtime_written=False,
    )
    assert validation["status"] == "fail"
    assert any("stale executable blocker" in issue for issue in validation["issues"])


def test_n9b1c3_tracked_files_do_not_embed_windows_absolute_paths():
    tracked = [
        ROOT / "src" / "legsa_gins" / "reporting" / "by2_n9b1c3_execution_matrix_hygiene_dependency_order.py",
        ROOT / "scripts" / "experiments" / "run_n9b1c3_execution_matrix_hygiene_dependency_order.py",
        ROOT / "scripts" / "audit_n9b1c3_execution_matrix_hygiene_dependency_order.py",
        ROOT / "tests" / "audit" / "test_n9b1c3_execution_matrix_hygiene_dependency_order.py",
        Path(__file__),
    ]
    windows_prefix = "C:" + "\\Users\\"
    posix_prefix = "C:" + "/Users/"
    for path in tracked:
        text = path.read_text(encoding="utf-8")
        assert windows_prefix not in text
        assert posix_prefix not in text
