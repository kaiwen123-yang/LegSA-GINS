import json
from pathlib import Path

from legsa_gins.reporting.by2_n9b1g2_selected_feedback_command_json_sync_fix import (
    FORBIDDEN_RUNTIME_OUTPUT_NAMES,
    SELECTED_FEEDBACK_ALGORITHM,
    SINGLE_BASELINE_ALGORITHM,
    STAGE,
    classify_eval_nav_safety,
    default_n9b1g2_runtime_root,
    run_n9b1g2_selected_feedback_command_json_sync_fix,
    validate_n9b1g2_result,
)


ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path):
    runtime_root = tmp_path / "n9b1g2"
    result = run_n9b1g2_selected_feedback_command_json_sync_fix(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
    )
    validation = validate_n9b1g2_result(
        ROOT,
        runtime_root,
        result["n9b1d_ready_command_matrix"],
        result["command_json_sync_matrix"],
        result["wsl_dryrun_commands"],
        result["feedback_eval_nav_safety_audit_report"],
        runtime_written=True,
    )
    return runtime_root, result, validation


def test_default_runtime_root_uses_n9b1g2_stage():
    root = default_n9b1g2_runtime_root(ROOT)
    assert root.name == STAGE
    assert root.parts[-2].startswith("by2")


def test_command_jsons_match_matrix_and_are_synchronized(tmp_path):
    _, result, validation = _run(tmp_path)
    assert validation["status"] == "pass"
    active = [row for row in result["n9b1d_ready_command_matrix"] if row["run_allowed_in_N9B1D"] is True]
    assert len(active) == 64
    assert len(result["command_json_sync_matrix"]) == 64
    for row in active:
        path = Path(row["solver_command_json"])
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["solver_command_json"] == row["solver_command_json"]
        assert payload["command"] == row["command"]
        assert payload["case_id"] == row["case_id"]
        assert payload["algorithm"] == row["algorithm"]
        assert payload["stage"] == row["stage"]


def test_feedback_generation_uses_official_eval_nav_and_no_stale_baseline(tmp_path):
    _, result, validation = _run(tmp_path)
    assert validation["official_eval_feedback_generation_rows"] == 6
    assert validation["stale_stage1_baseline_eval_nav_count"] == 0
    assert validation["command_json_official_eval_feedback_generation_rows"] == 6
    assert validation["command_json_stale_stage1_baseline_eval_nav_count"] == 0
    rows = [
        row
        for row in result["n9b1d_ready_command_matrix"]
        if row["algorithm"] == SELECTED_FEEDBACK_ALGORITHM and row["stage"] == "selected_feedback_stage1_feedback_generation"
    ]
    assert rows
    for row in rows:
        blob = json.dumps(row, ensure_ascii=False)
        assert "--baseline-eval-nav" in row["command"]
        assert "/stage1_baseline_official_eval/EVAL_NAV.csv" in blob
        assert "/stage1_baseline/EVAL_NAV.csv" not in blob
        assert "future_solver_entry" not in blob
        assert "--normal-parity-mode" not in blob
        assert "--run-filter-csv" not in blob


def test_dependency_order_and_single_position_noise_medium_mapping_preserved(tmp_path):
    _, result, _ = _run(tmp_path)
    selected = [row for row in result["n9b1d_ready_command_matrix"] if row["algorithm"] == SELECTED_FEEDBACK_ALGORITHM]
    grouped = {}
    for row in selected:
        grouped.setdefault(row["case_id"], []).append(row)
    for case_id, rows in grouped.items():
        stages = [row["stage"] for row in sorted(rows, key=lambda item: item["dependency_order"])]
        if case_id in {"M_normal_baseline_repeat", "L_feedback_disabled"}:
            assert stages == ["selected_feedback_stage2_solver"]
        else:
            assert stages == [
                "selected_feedback_stage1_baseline_solver",
                "selected_feedback_stage1_official_eval",
                "selected_feedback_stage1_feedback_generation",
                "selected_feedback_stage2_solver",
            ]
    medium = [
        row
        for row in result["n9b1d_ready_command_matrix"]
        if row["case_id"] == "C_position_noise_medium" and row["algorithm"] == SINGLE_BASELINE_ALGORITHM
    ]
    assert medium
    assert medium[0]["underlying_runner"] == "KF-GINS-Baseline"


def test_feedback_eval_nav_safety_classification_and_static_audit(tmp_path):
    _, result, validation = _run(tmp_path)
    assert validation["feedback_eval_nav_safety_status"] == "pass"
    assert result["feedback_eval_nav_safety_audit_report"]["eval_nav_columns_read"] == [
        "height_m",
        "lat_deg",
        "lon_deg",
        "pitch_deg",
        "roll_deg",
        "time",
        "vd",
        "ve",
        "vn",
        "yaw_deg",
    ]
    assert classify_eval_nav_safety(["time", "lat_deg"])[0] == "pass"
    assert classify_eval_nav_safety(["time", "custom_state"])[0] == "conditional_pass_with_note"
    assert classify_eval_nav_safety(["time", "north_error_m"])[0] == "fail"


def test_wsl_dryrun_only_and_no_runtime_outputs(tmp_path):
    runtime_root, result, _ = _run(tmp_path)
    dryrun = result["wsl_dryrun_commands"]
    assert len(dryrun) == 64
    assert result["wsl_dryrun_report"]["dry_run_only"] is True
    assert all(row["dry_run"] is True for row in dryrun)
    assert all(row["executed"] is False and row["executed_solver"] is False for row in dryrun)
    assert not [path for path in runtime_root.rglob("*") if path.name in FORBIDDEN_RUNTIME_OUTPUT_NAMES]
    assert not list(runtime_root.rglob("*.png"))
    assert not list(runtime_root.rglob("*.pdf"))


def test_decision_ready_only_for_n9b1d_not_n9b2(tmp_path):
    _, result, validation = _run(tmp_path)
    assert validation["status"] == "pass"
    assert result["decision_report"]["status"] == "N9B1G2_command_json_sync_complete"
    assert result["decision_report"]["ready_for_N9B1D_solver_execution"] is True
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
