from pathlib import Path

from legsa_gins.reporting.by2_n9b1g2_selected_feedback_command_json_sync_fix import (
    MATRIX_STEMS,
    REQUIRED_SUBDIRS,
    REPORT_NAMES,
    run_n9b1g2_selected_feedback_command_json_sync_fix,
    validate_n9b1g2_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1g2_audit_contract(tmp_path):
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
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
    assert validation["active_command_rows"] == 64
    assert validation["command_json_sync_rows"] == 64
    assert validation["wsl_dryrun_rows"] == 64
    assert validation["feedback_eval_nav_safety_status"] == "pass"
    assert validation["stale_stage1_baseline_eval_nav_count"] == 0
    assert validation["command_json_stale_stage1_baseline_eval_nav_count"] == 0
    assert validation["command_json_payload_mismatch_count"] == 0
    assert validation["stale_output_root_count"] == 0
    assert validation["forbidden_command_token_count"] == 0
    for subdir in REQUIRED_SUBDIRS:
        assert (runtime_root / subdir).is_dir()
    assert not list(runtime_root.rglob("EVAL_NAV.csv"))
    assert not list(runtime_root.rglob("RUN_MANIFEST.json"))
    assert not list(runtime_root.rglob("*.nav"))
    assert not list(runtime_root.rglob("*.png"))
