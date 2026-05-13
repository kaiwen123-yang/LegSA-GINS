"""中文说明：测试 N8A1 yaw 环绕审计。"""

from legsa_gins.fgo.fgo_yaw_convention_audit import audit_yaw_convention, yaw_delta_deg


def test_yaw_delta_wraps_across_zero() -> None:
    assert yaw_delta_deg(1.0, 359.0) == 2.0
    assert yaw_delta_deg(359.0, 1.0) == -2.0


def test_yaw_convention_flags_wrap_averaging_artifact() -> None:
    ekf = [{"time": 0, "yaw_deg": 359.0}, {"time": 1, "yaw_deg": 1.0}]
    fgo = [{"time": 0, "yaw_deg": 180.0}, {"time": 1, "yaw_deg": 120.0}]
    report = audit_yaw_convention(ekf_rows=ekf, fgo_rows=fgo)
    assert report["yaw_unit_consistent"] is True
    assert report["yaw_wrap_consistent"] is False
    assert report["yaw_residual_wrap_used"] is False
    assert report["blocker_status"] == "yaw_wrap_residual_blocker"
