"""中文说明：单元测试覆盖 N7C5 Go2 relative odometry 增量候选。"""

from legsa_gins.go2_prior.go2_relative_odometry_candidate import build_go2_relative_odometry_candidate


def test_relative_odometry_candidate_uses_increments_not_absolute_position_prior():
    rows = [
        {
            "time": index * 0.1,
            "aligned_time": index * 0.1,
            "go2_position_0": index * 0.1,
            "go2_position_1": index * 0.02,
            "go2_position_2": 0.0,
            "go2_velocity_0": 1.0,
            "go2_velocity_1": 0.2,
            "go2_velocity_2": 0.0,
        }
        for index in range(80)
    ]
    report = build_go2_relative_odometry_candidate(rows, step=10)
    assert report["relative_odometry_stability"] == "stable"
    assert report["ekf_absolute_position_prior_allowed"] is False
    assert report["go2_position_prior_enabled"] is False
    assert report["go2_position_truth_claim"] is False
