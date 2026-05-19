from pathlib import Path

from legsa_gins.reporting.by2_downsample_cadence_policy_repair import (
    OLD_DOWNSAMPLE_CASE_ID,
    REPAIRED_DOWNSAMPLE_CASE_ID,
    REPAIRED_PILOT_CASE_IDS,
    _apply_downsample_every_n,
    default_n9b1a1_runtime_root,
    run_downsample_cadence_policy_repair,
    validate_downsample_cadence_policy_repair,
)


ROOT = Path(__file__).resolve().parents[2]


def test_default_runtime_root_uses_n9b1a1_stage():
    root = default_n9b1a1_runtime_root(ROOT)
    assert root.parts[-2] == "by2\u6570\u636e\u96c6\u7ed8\u56fe\u5ba1\u8ba1"
    assert root.name == "N9B1A1_DOWNSAMPLE_CADENCE_POLICY_REPAIR"


def test_every2_downsample_keeps_rows_by_source_index():
    rows = [[float(i), i] for i in range(7)]
    output, mask = _apply_downsample_every_n(rows, 2)
    assert output == [rows[0], rows[2], rows[4], rows[6]]
    assert [row["kept"] for row in mask] == [True, False, True, False, True, False, True]
    assert all(row["keep_every_n"] == 2 for row in mask)


def test_repair_outputs_ready_pilot_without_solver_artifacts(tmp_path):
    runtime_root = tmp_path / "n9b1a1"
    result = run_downsample_cadence_policy_repair(ROOT, runtime_root=runtime_root, write_outputs=True)
    validation = validate_downsample_cadence_policy_repair(
        runtime_root,
        result["degraded_input_index_repaired"],
        result["random_value_index"],
        result["solver_command_plan_index_repaired"],
        result["pilot_ready_matrix_repaired"],
        True,
    )
    assert validation["status"] == "pass"
    cadence_rows = result["gnss_cadence_audit"]
    assert {"single7_clean_input", "dual15_clean_input", "gnss1_status_source", "final_v23_15col_source"} <= {
        row["source_id"] for row in cadence_rows
    }
    for row in cadence_rows:
        for key in [
            "path",
            "row_count",
            "time_start",
            "time_end",
            "duration",
            "median_dt",
            "p95_dt",
            "estimated_hz",
            "supports_5Hz_downsample",
            "supports_2Hz_downsample",
            "supports_1Hz_downsample",
            "supports_ratio_every2",
            "supports_ratio_every5",
            "source_role",
            "approved_for_current_runner",
        ]:
            assert key in row
    assert not any(row["approved_for_current_runner"] and row["supports_2Hz_downsample"] for row in cadence_rows)
    assert [row["case_id"] for row in result["pilot_case_plan_repaired"]] == REPAIRED_PILOT_CASE_IDS
    assert len(result["pilot_ready_matrix_repaired"]) == 10
    assert all(row["ready_for_N9B1B_solver_execution"] for row in result["pilot_ready_matrix_repaired"])
    degraded_cases = {row["case_id"] for row in result["degraded_input_index_repaired"]}
    assert REPAIRED_DOWNSAMPLE_CASE_ID in degraded_cases
    assert OLD_DOWNSAMPLE_CASE_ID not in degraded_cases
    assert not any(row["case_id"] == REPAIRED_DOWNSAMPLE_CASE_ID for row in result["random_value_index"])
    assert any(row["case_id"] == OLD_DOWNSAMPLE_CASE_ID and row["repair_status"].startswith("blocked") for row in result["full_matrix_downsample_repair"])
    assert result["decision_report"]["status"] == "N9B1A1_downsample_cadence_repair_complete"
    assert result["decision_report"]["ready_for_solver_execution"] is False
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))


def test_n9b1a1_tracked_files_do_not_embed_local_absolute_paths():
    tracked = [
        ROOT / "src" / "legsa_gins" / "reporting" / "by2_downsample_cadence_policy_repair.py",
        ROOT / "scripts" / "experiments" / "run_n9b1a1_downsample_cadence_policy_repair.py",
        ROOT / "scripts" / "audit_n9b1a1_downsample_cadence_policy_repair.py",
        Path(__file__),
    ]
    windows_prefix = "C:" + "\\Users\\"
    posix_prefix = "C:" + "/Users/"
    for path in tracked:
        text = path.read_text(encoding="utf-8")
        assert windows_prefix not in text
        assert posix_prefix not in text
