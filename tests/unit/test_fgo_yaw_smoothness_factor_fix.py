"""中文说明：测试 yaw smoothness wrap 修复。"""

from legsa_gins.fgo.fgo_yaw_smoothness_factor_fix import build_yaw_smoothness_fix_report, smooth_yaw_series_deg, yaw_smoothness_residual_series


def test_yaw_smoothness_uses_shortest_angle() -> None:
    residuals = yaw_smoothness_residual_series([359.0, 1.0, 2.0])
    assert residuals[0] == 2.0
    assert max(abs(value) for value in residuals) < 5.0


def test_smooth_yaw_series_does_not_arithmetic_average_wrap() -> None:
    smoothed = smooth_yaw_series_deg([359.0, 1.0, 2.0])
    assert all(value < 30.0 or value > 330.0 for value in smoothed)
    assert build_yaw_smoothness_fix_report()["smoothness_factor_deleted"] is False
