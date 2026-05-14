"""中文说明：测试 FGO yaw angle wrap 工具。"""

import math

import pytest

from legsa_gins.fgo.fgo_angle_utils import shortest_angle_residual_deg, shortest_angle_residual_rad, unwrap_series_deg, wrap_deg, wrap_rad


def test_shortest_angle_residual_wraps_deg() -> None:
    assert shortest_angle_residual_deg(359.0, 1.0) == -2.0
    assert shortest_angle_residual_deg(1.0, 359.0) == 2.0
    assert abs(shortest_angle_residual_deg(359.0, 1.0)) != 358.0


def test_shortest_angle_residual_wraps_rad_boundary() -> None:
    assert wrap_deg(180.0) == -180.0
    assert wrap_rad(math.pi) == -math.pi
    assert abs(shortest_angle_residual_rad(-math.pi + 0.01, math.pi - 0.01) - 0.02) < 1e-9


def test_unwrap_series_and_nan_policy() -> None:
    assert unwrap_series_deg([359.0, 1.0, 2.0]) == [359.0, 361.0, 362.0]
    with pytest.raises(ValueError):
        wrap_deg(float("nan"))
