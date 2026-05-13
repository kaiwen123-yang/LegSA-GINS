"""中文说明：单元测试覆盖 N7C5 yaw-rate consistency 候选审查。"""

from legsa_gins.go2_prior.go2_yawrate_consistency_candidate import build_go2_yawrate_consistency_candidate


def test_yawrate_candidate_detects_stable_go2_yawspeed():
    rows = [
        {"time": index * 0.1, "aligned_time": index * 0.1, "yaw_rad": 0.02 * index * 0.1, "yaw_speed_radps": 0.02, "gyro_z": 0.02}
        for index in range(30)
    ]
    report = build_go2_yawrate_consistency_candidate(rows, [{"phase": "turning"}] * 3)
    assert report["stability_status"] == "stable"
    assert report["ekf_direct_yawrate_factor_supported"] is False
    assert report["go2_yaw_prior_enabled"] is False
    assert report["go2_yawrate_truth_claim"] is False
