"""中文说明：weak prior builder 只生成 roll/pitch prior，不启用位置/速度/yaw。"""

from legsa_gins.go2_state.go2_weak_prior_builder import build_go2_attitude_weak_priors


def test_go2_weak_prior_builder_produces_roll_pitch_prior():
    rows = [{"aligned_time": "0.1", "roll_rad": "0.01", "pitch_rad": "-0.02", "mode": "1", "gait_type": "2"}]
    priors, report = build_go2_attitude_weak_priors(
        rows,
        quaternion_report={"activation_allowed_for_attitude_prior": True},
        frame_report={"activation_allowed": True},
        time_report={"activation_allowed": True, "overlap_start": 0.0, "overlap_end": 1.0},
    )
    assert len(priors) == 1
    assert report["valid_prior_count"] == 1
    assert report["yaw_prior_enabled"] is False
    assert report["position_prior_enabled"] is False
    assert report["velocity_prior_enabled"] is False
