"""中文说明：runtime yaw diagnostics 单元测试只检查决策边界。"""

from legsa_gins.evaluation.yaw_runtime_path_diagnostics import classify_yaw_runtime_issue


def _path_report(input_status: str = "input_paths_match", nav_status: str = "position_close_yaw_diverged") -> dict:
    return {
        "actual_input_vs_replay_input_yaw": {"input_path_parity_status": input_status},
        "actual_nav_vs_replay_nav_yaw": {
            "nav_path_parity_status": nav_status,
            "nav_yaw_diff_rmse_deg": 0.4 if nav_status == "nav_yaw_paths_match" else 90.0,
        },
        "actual_input_vs_actual_nav_yaw": {"classification": "nav_applies_yaw_transform"},
        "replay_input_vs_replay_nav_yaw": {"classification": "nav_tracks_input_yaw"},
    }


def test_input_mismatch_recommends_input_generation_fix() -> None:
    report = classify_yaw_runtime_issue(_path_report(input_status="input_yaw_mismatch"), {}, {})
    assert report["recommended_next_stage"] == "N4H2C_input_generation_fix"
    assert report["trace_solver_input"] is False


def test_config_missing_recommends_recovery_without_source_variant() -> None:
    report = classify_yaw_runtime_issue(
        _path_report(),
        {"actual_config_status": "evidence_missing", "evidence_missing": ["actual_runtime_config"]},
        {"current_source_audit": {}, "source_history": {"candidate_commit_count": 0}},
    )
    assert report["recommended_next_stage"] == "N4H2C_actual_config_recovery_needed"
    assert report["likely_issue_classification"]["config_evidence_missing"] is True


def test_source_variant_takes_runtime_parity_path() -> None:
    report = classify_yaw_runtime_issue(
        _path_report(),
        {"actual_config_status": "evidence_missing", "evidence_missing": ["actual_runtime_config"]},
        {
            "current_source_audit": {"current_yaw_measurement_transform": "direct_gnssdata_yaw_likely"},
            "source_history": {"candidate_commit_count": 2, "evidence_of_yaw_transform_variants": True},
        },
    )
    assert report["recommended_next_stage"] == "N4H2C_source_version_parity_replay"
    assert report["full_kfgins_framework_needed"] is True


def test_nav_match_but_summary_yaw_diverges_flags_reference_mapping() -> None:
    report = classify_yaw_runtime_issue(
        _path_report(nav_status="nav_yaw_paths_match"),
        {"actual_config_status": "evidence_missing", "evidence_missing": ["actual_runtime_config"]},
        {"current_source_audit": {}, "source_history": {}},
        actual_summary={"yaw_rmse_deg": 1.8},
        replay_summary={"yaw_rmse_deg": 93.5},
    )
    assert report["recommended_next_stage"] == "N4H2C_replay_reference_mapping_or_summary_staleness_audit"
    assert report["likely_issue_classification"]["likely_replay_reference_mapping_or_summary_staleness"] is True
