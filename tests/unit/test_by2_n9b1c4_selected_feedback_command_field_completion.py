from pathlib import Path

from legsa_gins.reporting.by2_n9b1c4_selected_feedback_command_field_completion import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1c4_selected_feedback_command_field_completion,
    validate_n9b1c4_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1c4_completes_selected_feedback_runner_fields(tmp_path):
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
    assert result["decision_report"]["status"] == "N9B1C4_selected_feedback_command_fields_complete"
    assert result["decision_report"]["ready_for_N9B1D_solver_execution"] is True
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()

    selected = [
        row
        for row in result["n9b1d_ready_command_matrix"]
        if row["algorithm"] == "selected_feedback_EKF" and row.get("run_allowed_in_N9B1D") is True
    ]
    assert len(selected) == 8
    assert not [row for row in selected if not row["entrypoint"]]
    assert not [row for row in selected if not row["working_directory"]]
    assert not [row for row in selected if not row["solver_command_json"]]
    assert all(row["solver_command_json"].startswith("command_matrix_completion/") for row in selected)
    assert all((runtime_root / row["solver_command_json"]).is_file() for row in selected)
    assert not [row for row in selected if "future_solver_entry" in row["command"]]


def test_n9b1c4_dependency_wording_counts_are_precise(tmp_path):
    result = run_n9b1c4_selected_feedback_command_field_completion(
        ROOT,
        runtime_root=tmp_path / "n9b1c4",
        write_outputs=True,
        run_wsl_dryrun_refresh=False,
    )
    report = result["dependency_graph_cleanup_report"]
    assert report["same_case_selected_feedback_cases"] == 6
    assert report["same_case_selected_feedback_edges"] == 12
    assert report["baseline_to_feedback_to_selected_edges"] == 12
    assert report["dependency_semantics_changed"] is False


def test_n9b1c4_validation_rejects_blank_solver_command_json(tmp_path):
    result = run_n9b1c4_selected_feedback_command_field_completion(
        ROOT,
        runtime_root=tmp_path / "n9b1c4",
        write_outputs=True,
        run_wsl_dryrun_refresh=False,
    )
    rows = [dict(row) for row in result["n9b1d_ready_command_matrix"]]
    target = next(row for row in rows if row["algorithm"] == "selected_feedback_EKF" and row.get("run_allowed_in_N9B1D") is True)
    target["solver_command_json"] = ""
    validation = validate_n9b1c4_result(
        ROOT,
        tmp_path / "n9b1c4",
        rows,
        result["command_field_completion_diff"],
        result["wsl_dryrun_refresh"],
        result["dependency_graph_cleanup_report"],
        runtime_written=False,
    )
    assert validation["status"] == "fail"
    assert any("blank solver_command_json" in issue for issue in validation["issues"])


def test_n9b1c4_tracked_files_do_not_embed_windows_absolute_paths():
    tracked = [
        ROOT / "src" / "legsa_gins" / "reporting" / "by2_n9b1c4_selected_feedback_command_field_completion.py",
        ROOT / "scripts" / "experiments" / "run_n9b1c4_selected_feedback_command_field_completion.py",
        ROOT / "scripts" / "audit_n9b1c4_selected_feedback_command_field_completion.py",
        ROOT / "tests" / "audit" / "test_n9b1c4_selected_feedback_command_field_completion.py",
        Path(__file__),
    ]
    windows_prefix = "C:" + "\\Users\\"
    posix_prefix = "C:" + "/Users/"
    for path in tracked:
        text = path.read_text(encoding="utf-8")
        assert windows_prefix not in text
        assert posix_prefix not in text
