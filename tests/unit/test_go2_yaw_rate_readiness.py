"""中文说明：yaw-rate readiness 不启用 yaw prior。"""

from legsa_gins.go2_prior.go2_yaw_rate_readiness import analyze_yaw_rate_readiness


def test_go2_yaw_rate_readiness_stable_for_future_review():
    rows = [{"aligned_time": i * 0.1, "yaw_rad": i * 0.02, "yaw_speed_radps": 0.2} for i in range(20)]
    _, report = analyze_yaw_rate_readiness(rows)
    assert report["yaw_speed_available"] is True
    assert report["consistency_status"] == "stable_for_future_review"
    assert report["yaw_rate_prior_recommended"] == "conditional"
    assert report["go2_yaw_prior_enabled"] is False
