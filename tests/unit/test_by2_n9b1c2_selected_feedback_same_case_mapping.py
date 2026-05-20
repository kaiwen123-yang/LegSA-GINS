from pathlib import Path

from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (
    L_DISABLED_CASE,
    M_CLEAN_REPEAT_CASE,
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1c2_selected_feedback_same_case_mapping,
    validate_n9b1c2_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_n9b1c2_maps_selected_feedback_with_same_case_plan(tmp_path):
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
    mapped = [row for row in result["selected_feedback_mapping_matrix"] if row["mapping_status"] == "mapped"]
    assert mapped
    assert all(row["run_allowed_in_N9B1D"] is True for row in mapped)
    assert not [row for row in result["selected_feedback_mapping_matrix"] if row["routing_status"] == "not_selected_in_prior_plan"]
    assert {row["case_id"] for row in mapped} == {
        "A_outage_5s",
        "B_gnss_downsample_every2",
        "C_position_noise_medium",
        "D_position_spike_medium",
        "H_dual_yaw_noise_medium",
        "J_go2_horizontal_velocity_missing",
        L_DISABLED_CASE,
        M_CLEAN_REPEAT_CASE,
    }
    assert not [row for row in mapped if row["case_id"] not in {M_CLEAN_REPEAT_CASE, L_DISABLED_CASE} and not row["stage1_plan_exists"]]
    assert not [row for row in mapped if row["case_id"] not in {M_CLEAN_REPEAT_CASE, L_DISABLED_CASE} and not row["stage2_plan_exists"]]
    assert not [row for row in result["selected_feedback_mapping_matrix"] if row["clean_n8j_path_used_for_degraded_case"]]
    assert all(row["dry_run_only"] is True and row["executed"] is False for row in result["wsl_dryrun_command_matrix"])


def test_n9b1c2_validation_rejects_clean_feedback_for_degraded_case(tmp_path):
    runtime_root = tmp_path / "n9b1c2"
    result = run_n9b1c2_selected_feedback_same_case_mapping(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=False,
    )
    rows = [dict(row) for row in result["selected_feedback_mapping_matrix"]]
    target = next(row for row in rows if row["case_id"] not in {M_CLEAN_REPEAT_CASE, L_DISABLED_CASE})
    target["clean_n8j_path_used_for_degraded_case"] = True
    validation = validate_n9b1c2_result(
        ROOT,
        runtime_root,
        rows,
        result["repaired_command_plan_matrix"],
        result["wsl_dryrun_command_matrix"],
        runtime_written=False,
    )
    assert validation["status"] == "fail"
    assert any("clean N8J feedback path" in issue for issue in validation["issues"])


def test_n9b1c2_tracked_files_do_not_embed_windows_absolute_paths():
    tracked = [
        ROOT / "src" / "legsa_gins" / "reporting" / "by2_n9b1c2_selected_feedback_same_case_mapping.py",
        ROOT / "scripts" / "experiments" / "run_n9b1c2_selected_feedback_same_case_mapping.py",
        ROOT / "scripts" / "audit_n9b1c2_selected_feedback_same_case_mapping.py",
        ROOT / "tests" / "audit" / "test_n9b1c2_selected_feedback_same_case_mapping.py",
        Path(__file__),
    ]
    windows_prefix = "C:" + "\\Users\\"
    posix_prefix = "C:" + "/Users/"
    for path in tracked:
        text = path.read_text(encoding="utf-8")
        assert windows_prefix not in text
        assert posix_prefix not in text
