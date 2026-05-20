from pathlib import Path

from legsa_gins.reporting.by2_n9b1c1_routing_command_consistency import (
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1c1_routing_command_consistency_fix,
    validate_n9b1c1_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1c1_routing_and_selected_feedback_contract(tmp_path):
    runtime_root = tmp_path / "n9b1c1"
    result = run_n9b1c1_routing_command_consistency_fix(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
    )
    validation = validate_n9b1c1_result(
        runtime_root,
        result["command_mapping_matrix_repaired"],
        result["wsl_dryrun_command_matrix"],
        runtime_written=True,
    )
    assert validation["status"] == "pass"
    for name in REPORT_NAMES:
        assert (runtime_root / "reports" / name).is_file()
    for stem in MATRIX_STEMS:
        assert (runtime_root / "matrix" / f"{stem}.csv").is_file()
        assert (runtime_root / "matrix" / f"{stem}.json").is_file()
    rows = result["command_mapping_matrix_repaired"]
    assert not [
        row
        for row in rows
        if row["routing_status"] == "not_selected_in_prior_plan"
        and (row["mapping_status"] == "mapped" or row["run_allowed_in_N9B1D"] or row["command"])
    ]
    assert not [
        row
        for row in rows
        if row["mapping_status"] == "fixed_reference" and (row["command"] or row["run_allowed_in_N9B1D"])
    ]
    assert not [row for row in rows if "future_solver_entry" in row["command"]]
    assert not [
        row
        for row in rows
        if row["algorithm"] == "selected_feedback_EKF"
        and row["case_id"] not in {"M_normal_baseline_repeat", "L_feedback_disabled"}
        and row["mapping_status"] == "mapped"
    ]
    assert all(row["dry_run_only"] is True and row["executed"] is False for row in result["wsl_dryrun_command_matrix"])


def test_n9b1c1_tracked_files_do_not_embed_windows_absolute_paths():
    tracked = [
        ROOT / "src" / "legsa_gins" / "reporting" / "by2_n9b1c1_routing_command_consistency.py",
        ROOT / "scripts" / "experiments" / "run_n9b1c1_routing_command_consistency_fix.py",
        ROOT / "scripts" / "audit_n9b1c1_routing_command_consistency_fix.py",
        Path(__file__),
    ]
    windows_prefix = "C:" + "\\Users\\"
    posix_prefix = "C:" + "/Users/"
    for path in tracked:
        text = path.read_text(encoding="utf-8")
        assert windows_prefix not in text
        assert posix_prefix not in text
