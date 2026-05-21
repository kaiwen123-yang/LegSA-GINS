from pathlib import Path

from legsa_gins.reporting.by2_n9b1g1_selected_feedback_stage1_eval_dependency_fix import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1g1_selected_feedback_stage1_eval_dependency_fix,
    validate_n9b1g1_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1g1_audit_contract(tmp_path):
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
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
    assert validation["selected_feedback_stage1_official_eval_rows"] == 6
    assert validation["stale_root_count_active_command_fields"] == 0
    assert validation["new_root_count_active_command_fields"] > 0
    assert validation["single_position_noise_guard_status"] == "pass"
    assert not list(runtime_root.rglob("EVAL_NAV.csv"))
    assert not list(runtime_root.rglob("RUN_MANIFEST.json"))
    assert not list(runtime_root.rglob("*.nav"))
    assert not list(runtime_root.rglob("*.png"))
