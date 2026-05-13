"""Unit tests for N7C6 joint factor Jacobian.

中文说明：测试 N7C6 joint factor Jacobian 边界。
"""

from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_jacobian import build_joint_factor_jacobian_contract


def test_joint_factor_jacobian_contract_boundary():
    report = build_joint_factor_jacobian_contract()
    assert report["finite_difference_check_status"] == "toy_passed"
    assert "velocity_down" in report["zero_state_blocks"]
    assert "attitude_yaw" in report["zero_state_blocks"]
    assert report["vertical_velocity_disabled"] is True
