"""中文说明：fresh replay evaluator 单元测试只使用 toy rows。"""

from legsa_gins.evaluation.fresh_replay_evaluator import (
    compare_fresh_replay_to_dual_summary,
    evaluate_replay_against_official_reference,
)


def test_fresh_replay_evaluator_expected_yaw(tmp_path) -> None:
    replay = [
        {"timestamp": 0.0, "time": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
        {"timestamp": 1.0, "time": 1.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
    ]
    reference = [
        {"timestamp": 0.0, "time": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 8.0},
        {"timestamp": 1.0, "time": 1.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 8.0},
    ]
    report = evaluate_replay_against_official_reference(replay, reference, tmp_path)
    summary = report["fresh_summary"]
    assert summary["yaw_rmse_deg"] == 2.0
    assert summary["yaw_gate_pass"] is True
    assert report["solver_output_changed"] is False


def test_yaw_above_two_does_not_pass_gate() -> None:
    comparison = compare_fresh_replay_to_dual_summary(
        {"horizontal_rmse_m": 0.35, "up_rmse_m": 0.8, "yaw_rmse_deg": 2.06, "roll_rmse_deg": 1.0, "pitch_rmse_deg": 1.5},
        {"horizontal_rmse_m": 0.35, "up_rmse_m": 0.8, "yaw_rmse_deg": 1.81, "roll_rmse_deg": 1.0, "pitch_rmse_deg": 1.5},
    )
    assert comparison["yaw_gate_pass"] is False
    assert comparison["fresh_replay_close_to_dual_final_v23"] is True
    assert comparison["formal_claim_allowed"] is False
