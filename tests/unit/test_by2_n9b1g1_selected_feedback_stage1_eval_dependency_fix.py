from pathlib import Path

from legsa_gins.reporting.by2_n9b1g1_selected_feedback_stage1_eval_dependency_fix import (
    N9B1D_STAGE,
    SAME_CASE_SELECTED_FEEDBACK_CASES,
    SELECTED_FEEDBACK_ALGORITHM,
    SINGLE_BASELINE_ALGORITHM,
    STAGE,
    default_n9b1g1_runtime_root,
    run_n9b1g1_selected_feedback_stage1_eval_dependency_fix,
    validate_n9b1g1_result,
)


ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path):
    runtime_root = tmp_path / "n9b1g1"
    result = run_n9b1g1_selected_feedback_stage1_eval_dependency_fix(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
    )
    validation = validate_n9b1g1_result(
        ROOT,
        runtime_root,
        result["n9b1d_ready_command_matrix"],
        result["wsl_dryrun_commands"],
        result["single_position_noise_guard_matrix"],
        runtime_written=True,
    )
    return runtime_root, result, validation


def test_default_runtime_root_uses_n9b1g1_stage():
    root = default_n9b1g1_runtime_root(ROOT)
    assert root.name == STAGE
    assert root.parts[-2].startswith("by2")


def test_same_case_selected_feedback_has_stage1_official_eval_dependency(tmp_path):
    _, result, validation = _run(tmp_path)
    assert validation["status"] == "pass"
    rows = [
        row
        for row in result["n9b1d_ready_command_matrix"]
        if row["algorithm"] == SELECTED_FEEDBACK_ALGORITHM and row["case_id"] in SAME_CASE_SELECTED_FEEDBACK_CASES
    ]
    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(row)
    for case_id in SAME_CASE_SELECTED_FEEDBACK_CASES:
        stages = [row["stage"] for row in sorted(by_case[case_id], key=lambda row: row["dependency_order"])]
        assert stages == [
            "selected_feedback_stage1_baseline_solver",
            "selected_feedback_stage1_official_eval",
            "selected_feedback_stage1_feedback_generation",
            "selected_feedback_stage2_solver",
        ]


def test_feedback_generation_consumes_stage1_official_eval_nav(tmp_path):
    _, result, _ = _run(tmp_path)
    rows = result["feedback_generation_commands"]
    assert len(rows) == len(SAME_CASE_SELECTED_FEEDBACK_CASES)
    assert all("/stage1_baseline_official_eval/EVAL_NAV.csv" in row["baseline_eval_nav_dependency"] for row in rows)
    assert all("--baseline-eval-nav" in row["command"] for row in rows)
    assert all("stage1_baseline_official_eval/EVAL_NAV.csv" in row["command"] for row in rows)


def test_output_roots_are_normalized_to_n9b1d_execution_and_evaluation(tmp_path):
    _, result, validation = _run(tmp_path)
    assert validation["stale_root_count_active_command_fields"] == 0
    assert validation["new_root_count_active_command_fields"] > 0
    active = [row for row in result["n9b1d_ready_command_matrix"] if row["run_allowed_in_N9B1D"] is True]
    assert any(N9B1D_STAGE in row["command"] for row in active)
    assert not any("N9B1D_PILOT_SOLVER_EXECUTION/" in row["command"] for row in active)
    assert not any("_n9b1g_source_not_written" in row["command"] for row in active)


def test_command_plan_paths_are_materialized_and_use_formal_runner_output_names(tmp_path):
    _, result, validation = _run(tmp_path)
    assert validation["status"] == "pass"
    active = [row for row in result["n9b1d_ready_command_matrix"] if row["run_allowed_in_N9B1D"] is True]
    for row in active:
        if row.get("runtime_config_path"):
            assert Path(row["runtime_config_path"]).is_file()
        if row.get("solver_command_json"):
            assert Path(row["solver_command_json"]).is_file()
    official_eval = [row for row in active if row["stage"] == "selected_feedback_stage1_official_eval"]
    assert official_eval
    assert all("LegSA_PORT_NAV.nav" in row["command"] for row in official_eval)
    assert all("LegSA_PORT_STD.csv" in row["command"] for row in official_eval)
    assert not any("LegSA_NAV.nav" in row["command"] for row in official_eval)
    assert not any("LegSA_STD.csv" in row["command"] for row in official_eval)


def test_single_position_noise_guard_keeps_medium_single_baseline_on_kfgins(tmp_path):
    _, result, _ = _run(tmp_path)
    guard = result["single_position_noise_guard_matrix"]
    assert all(row["n9b0a1_applicable"] is True for row in guard)
    medium = [
        row
        for row in result["n9b1d_ready_command_matrix"]
        if row["case_id"] == "C_position_noise_medium" and row["algorithm"] == SINGLE_BASELINE_ALGORITHM
    ]
    assert medium
    assert medium[0]["underlying_runner"] == "KF-GINS-Baseline"
    assert "legsa_gins.reporting.by2_algorithm_runner" not in medium[0]["command"]


def test_wsl_rows_are_dryrun_only_and_no_runtime_outputs(tmp_path):
    runtime_root, result, _ = _run(tmp_path)
    assert result["wsl_dryrun_report"]["dry_run_only"] is True
    assert all(row["dry_run"] is True for row in result["wsl_dryrun_commands"])
    assert all(row["executed"] is False and row["executed_solver"] is False for row in result["wsl_dryrun_commands"])
    forbidden_names = {
        "LegSA_NAV.nav",
        "LegSA_STD.csv",
        "LegSA_PORT_NAV.nav",
        "LegSA_PORT_STD.csv",
        "KF_GINS_Navresult.nav",
        "KF_GINS_STD.txt",
        "EVAL_NAV.csv",
        "RUN_MANIFEST.json",
    }
    assert not [path for path in runtime_root.rglob("*") if path.name in forbidden_names]


def test_json_outputs_are_utf8_without_bom(tmp_path):
    runtime_root, _, _ = _run(tmp_path)
    json_paths = list(runtime_root.rglob("*.json"))
    assert json_paths
    assert not [path for path in json_paths if path.read_bytes().startswith(b"\xef\xbb\xbf")]
