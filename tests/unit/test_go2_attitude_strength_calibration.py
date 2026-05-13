"""Unit tests for N7C6 attitude strength calibration.

中文说明：测试 Go2 roll/pitch std 扫描 prior 构造。
"""

from legsa_gins.go2_prior.go2_attitude_strength_calibration import build_attitude_strength_prior_rows, summarize_attitude_prior_rows


def test_attitude_strength_rows_are_not_truth():
    rows = build_attitude_strength_prior_rows(
        [{"time": 0.0, "aligned_time": 0.0, "roll_rad": 0.01, "pitch_rad": -0.02, "mode": "walk", "gait_type": "trot"}],
        std_deg=1.6,
    )
    assert rows[0]["go2_roll_pitch_truth_claim"] == "false"
    report = summarize_attitude_prior_rows(rows, std_deg=1.6)
    assert report["go2_yaw_prior_enabled"] is False
