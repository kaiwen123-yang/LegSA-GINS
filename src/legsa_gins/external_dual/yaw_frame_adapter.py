"""Yaw-frame helpers for the BY2 lateral dual-antenna layout."""

from __future__ import annotations

import math


FIXED_LATERAL_TO_BODY_OFFSET_DEG = 90.0


def wrap360_deg(angle_deg: float) -> float:
    return angle_deg % 360.0


def yaw_error_deg(estimate_deg: float, reference_deg: float) -> float:
    return (estimate_deg - reference_deg + 180.0) % 360.0 - 180.0


def circular_mean_deg(values: list[float], weights: list[float] | None = None) -> float:
    if not values:
        raise ValueError("circular_mean_deg requires at least one value")
    weights = weights or [1.0] * len(values)
    x = sum(math.cos(math.radians(value)) * weight for value, weight in zip(values, weights))
    y = sum(math.sin(math.radians(value)) * weight for value, weight in zip(values, weights))
    return wrap360_deg(math.degrees(math.atan2(y, x)))


def baseline_heading_ned_deg(north_m: float, east_m: float) -> float:
    return wrap360_deg(math.degrees(math.atan2(east_m, north_m)))


def baseline_heading_to_body_yaw_ned_deg(baseline_heading_deg: float) -> float:
    """Apply the locked BY2 GNSS1-right/GNSS2-left lateral +90 deg policy."""

    return wrap360_deg(baseline_heading_deg + FIXED_LATERAL_TO_BODY_OFFSET_DEG)


def wrap_safe_body_yaw_residual_deg(method_body_yaw_deg: float, reference_body_yaw_deg: float) -> float:
    return yaw_error_deg(method_body_yaw_deg, reference_body_yaw_deg)
