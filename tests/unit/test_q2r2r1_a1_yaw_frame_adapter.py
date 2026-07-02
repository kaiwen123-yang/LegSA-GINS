from legsa_gins.external_dual.yaw_frame_adapter import baseline_heading_to_body_yaw_ned_deg, wrap_safe_body_yaw_residual_deg


def test_a1_lateral_plus90_policy_is_fixed():
    assert baseline_heading_to_body_yaw_ned_deg(0.0) == 90.0
    assert baseline_heading_to_body_yaw_ned_deg(270.0) == 0.0


def test_a1_residual_is_wrap_safe():
    assert wrap_safe_body_yaw_residual_deg(1.0, 359.0) == 2.0
    assert wrap_safe_body_yaw_residual_deg(359.0, 1.0) == -2.0
