"""中文说明：runtime config audit 单元测试只使用 toy config。"""

from legsa_gins.source_audit.runtime_yaw_update_config_audit import (
    compare_actual_and_replay_config,
    find_runtime_configs,
)


def test_actual_config_missing_recommends_recovery() -> None:
    report = compare_actual_and_replay_config(None, {"extracted_fields": {"initatt": [0.0, 0.0, 1.0]}})
    assert report["actual_config_status"] == "evidence_missing"
    assert report["recommended_action"] == "manual_actual_config_recovery_or_source_history_audit"
    assert report["trace_solver_input"] is False
    assert report["output_only_correction"] is False


def test_initatt_yaw_diff_is_yaw_relevant() -> None:
    report = compare_actual_and_replay_config(
        {"extracted_fields": {"initatt": [0.0, 0.0, 1.0], "antlever": [0.0, 0.0, -0.25]}},
        {"extracted_fields": {"initatt": [0.0, 0.0, 3.5], "antlever": [0.0, 0.0, -0.25]}},
    )
    assert report["significant_yaw_config_diff"] is True
    assert report["yaw_relevant_config_diff"]["initatt_yaw_diff_deg"] == 2.5


def test_find_runtime_configs_parses_yaml(tmp_path) -> None:
    replay = tmp_path / "n4h2" / "replay"
    replay.mkdir(parents=True)
    (replay / "kf-gins-n4h2-replay.yaml").write_text(
        "imupath: a.imu\n"
        "gnsspath: a.gnss\n"
        "initatt:\n"
        "- 0.0\n"
        "- 0.0\n"
        "- 0.7\n"
        "antlever:\n"
        "- 0.0\n"
        "- 0.0\n"
        "- -0.25\n",
        encoding="utf-8",
    )
    report = find_runtime_configs({"N4H2_ARTIFACTS_ROOT": tmp_path / "n4h2"})
    assert report["replay_config_status"] == "parsed"
    assert report["best_replay_config"]["extracted_fields"]["initatt"] == [0.0, 0.0, 0.7]
