from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry


def test_factor_registry_contains_go2_joint_boundary() -> None:
    """中文说明：Go2 joint factor 不触碰 yaw/position/vertical velocity。"""
    registry = build_default_factor_registry()
    assert "Go2ProprioceptiveJointFactor" in registry["active_default_factors"]
    assert registry["go2_joint_factor_contract"]["no_yaw"] is True
    assert registry["go2_joint_factor_contract"]["go2_not_truth"] is True
