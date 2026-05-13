"""N7C policy unit tests.

中文说明：单测验证 N7C policy 只允许水平速度弱先验。
"""

from legsa_gins.go2_prior.go2_horizontal_velocity_prior_policy import build_n7c_policy, validate_n7c_policy


def test_n7c_policy_is_horizontal_only_and_no_truth_claim():
    policy = build_n7c_policy({"std_policy": {"base_std_mps": 2.0}})
    ok, blockers = validate_n7c_policy(policy)
    assert ok, blockers
    assert tuple(policy["measurement_components"]) == ("vn", "ve")
    assert policy["vertical_velocity_enabled"] is False
    assert policy["go2_yaw_prior_enabled"] is False
    assert policy["go2_position_prior_enabled"] is False
    assert policy["go2_velocity_truth_claim"] is False
    assert policy["paper_performance_claim"] is False


def test_n7c_policy_rejects_vertical_enable():
    policy = build_n7c_policy()
    policy["vertical_velocity_enabled"] = True
    ok, blockers = validate_n7c_policy(policy)
    assert ok is False
    assert "vertical_velocity_enabled" in blockers
