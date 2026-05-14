"""Angle utilities for FGO yaw residuals.

中文说明：角度工具只服务 FGO yaw residual / smoothness 约定，不使用 trace
或 final_v23 输出调权。
"""

from __future__ import annotations

import math


def _finite(value: float, *, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def wrap_rad(angle: float) -> float:
    """Wrap radians to [-pi, pi)."""
    value = _finite(angle, name="angle")
    return (value + math.pi) % (2.0 * math.pi) - math.pi


def wrap_deg(angle: float) -> float:
    """Wrap degrees to [-180, 180)."""
    value = _finite(angle, name="angle")
    return (value + 180.0) % 360.0 - 180.0


def shortest_angle_residual_rad(pred: float, obs: float) -> float:
    """Return wrap(pred - obs) in radians."""
    return wrap_rad(_finite(pred, name="pred") - _finite(obs, name="obs"))


def shortest_angle_residual_deg(pred: float, obs: float) -> float:
    """Return wrap(pred - obs) in degrees."""
    return wrap_deg(_finite(pred, name="pred") - _finite(obs, name="obs"))


def safe_angle_diff_rad(a: float, b: float) -> float:
    return shortest_angle_residual_rad(a, b)


def safe_angle_diff_deg(a: float, b: float) -> float:
    return shortest_angle_residual_deg(a, b)


def unwrap_series_rad(series: list[float]) -> list[float]:
    if not series:
        return []
    values = [_finite(value, name="series") for value in series]
    out = [values[0]]
    for value in values[1:]:
        out.append(out[-1] + shortest_angle_residual_rad(value, out[-1]))
    return out


def unwrap_series_deg(series: list[float]) -> list[float]:
    if not series:
        return []
    values = [_finite(value, name="series") for value in series]
    out = [values[0]]
    for value in values[1:]:
        out.append(out[-1] + shortest_angle_residual_deg(value, out[-1]))
    return out


def normalize_deg_0_360(angle: float) -> float:
    return _finite(angle, name="angle") % 360.0
