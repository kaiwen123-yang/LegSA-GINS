"""中文说明：replay reference mapping audit 单元测试使用 toy summary。"""

from legsa_gins.evaluation.replay_reference_mapping_audit import compare_old_summary_to_fresh


def test_old_yaw_93_fresh_yaw_2_triggers_mapping_mismatch() -> None:
    report = compare_old_summary_to_fresh(
        {"horizontal_rmse_m": 0.35, "up_rmse_m": 0.8, "yaw_rmse_deg": 93.0},
        {"horizontal_rmse_m": 0.36, "up_rmse_m": 0.82, "yaw_rmse_deg": 2.0},
        old_reference_source="trace_reference_reported",
    )
    assert report["reference_mapping_mismatch_likely"] is True
    assert report["stale_summary_or_wrong_reference_mapping"] is True
    assert report["trace_solver_input"] is False
