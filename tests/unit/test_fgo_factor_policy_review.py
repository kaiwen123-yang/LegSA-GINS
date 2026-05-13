"""中文说明：测试 N8A1 factor policy 默认栈边界。"""

from legsa_gins.fgo.fgo_factor_policy_review import review_factor_policy


def test_factor_policy_keeps_candidates_out_of_default() -> None:
    rows = [
        {"time": 0, "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": 0, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0},
        {"time": 1, "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": 1, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0},
    ]
    report = review_factor_policy(ekf_rows=rows, fgo_rows=rows)
    assert report["default_active_stack_valid"] is True
    assert report["diagnostic_candidates_not_default"] is True
    assert report["candidate_factor_leak_suspect"] is False
    assert "no_smoothness" in report["recommended_ablation"]
