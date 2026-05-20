from pathlib import Path

from legsa_gins.reporting.by2_n9b1g_case_level_command_rebind_with_formal_runner import (
    SELECTED_FEEDBACK_ALGORITHM,
    STAGE,
    default_n9b1g_runtime_root,
    run_n9b1g_case_level_command_rebind_with_formal_runner,
    validate_n9b1g_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_default_runtime_root_uses_n9b1g_stage():
    root = default_n9b1g_runtime_root(ROOT)
    assert root.name == STAGE
    assert root.parts[-2].startswith("by2")


def test_n9b1g_rebinds_case_level_formal_commands_without_normal_parity_mode(tmp_path):
    runtime_root = tmp_path / "n9b1g"
    result = run_n9b1g_case_level_command_rebind_with_formal_runner(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
    )
    rows = result["n9b1d_case_level_command_matrix"]
    validation = validate_n9b1g_result(
        ROOT,
        runtime_root,
        rows,
        result["wsl_dryrun_case_level_commands"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    assert result["command_rebind_report"]["source_case_algorithm_rows"] == 46
    assert result["command_rebind_report"]["formal_legsa_source_rows"] == 41
    assert result["command_rebind_report"]["single_baseline_source_rows"] == 5
    assert result["command_rebind_report"]["case_level_command_rows"] == 58
    assert result["command_rebind_report"]["selected_feedback_dependency_command_count"] == 20
    assert not any("--normal-parity-mode" in row["command"] for row in rows)
    assert not any("future_solver_entry" in row["command"] for row in rows)
    assert not any("--run-filter-csv" in row["command"] for row in rows)
    assert not any(row["case_id"] == "B_gnss_downsample_2Hz" for row in rows)
    formal_solver_rows = [
        row
        for row in rows
        if row["algorithm"] != "single_antenna_gnss1_status_KF_GINS"
        and row["stage"] != "selected_feedback_stage1_feedback_generation"
    ]
    assert all("legsa_gins.reporting.by2_algorithm_runner" in row["command"] for row in formal_solver_rows)
    assert all(row["runtime_config_path"] for row in rows)
    assert all(row["solver_command_json"] for row in rows)
    assert result["decision_report"]["ready_for_N9B2_execution"] is False


def test_n9b1g_selected_feedback_dependency_order_and_feedback_sources(tmp_path):
    runtime_root = tmp_path / "n9b1g"
    result = run_n9b1g_case_level_command_rebind_with_formal_runner(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
    )
    rows = [
        row
        for row in result["n9b1d_case_level_command_matrix"]
        if row["algorithm"] == SELECTED_FEEDBACK_ALGORITHM
    ]
    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(row)
    for case_rows in by_case.values():
        case_rows.sort(key=lambda row: row["dependency_order"])
    assert [row["stage"] for row in by_case["A_outage_5s"]] == [
        "selected_feedback_stage1_baseline",
        "selected_feedback_stage1_feedback_generation",
        "selected_feedback_stage2_solver",
    ]
    assert [row["stage"] for row in by_case["L_feedback_disabled"]] == ["selected_feedback_stage2_solver"]
    assert [row["stage"] for row in by_case["M_normal_baseline_repeat"]] == ["selected_feedback_stage2_solver"]
    degraded_rows = [row for row in rows if row["case_id"] != "M_normal_baseline_repeat"]
    assert not any("N8J_feedback_final_validation" in row.get("feedback_input", "") for row in degraded_rows)
    assert any("same_case_feedback_plan" in row.get("feedback_input", "") for row in by_case["A_outage_5s"])
