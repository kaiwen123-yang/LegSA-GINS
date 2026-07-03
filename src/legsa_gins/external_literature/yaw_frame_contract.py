"""Yaw-frame contract for lateral dual-antenna literature runs."""

from __future__ import annotations

import math


LATERAL_BASELINE_TO_BODY_OFFSET_DEG = 90.0


def wrap360_deg(angle_deg: float) -> float:
    return angle_deg % 360.0


def wrap180_deg(angle_deg: float) -> float:
    return (angle_deg + 180.0) % 360.0 - 180.0


def baseline_heading_ned_deg(north_m: float, east_m: float) -> float:
    return wrap360_deg(math.degrees(math.atan2(east_m, north_m)))


def baseline_heading_to_body_yaw_deg(baseline_heading_deg: float) -> float:
    """Locked BY2 physical convention: GNSS2-GNSS1 lateral heading plus 90 deg."""

    return wrap360_deg(baseline_heading_deg + LATERAL_BASELINE_TO_BODY_OFFSET_DEG)


def body_yaw_to_lateral_baseline_heading_deg(body_yaw_deg: float) -> float:
    return wrap360_deg(body_yaw_deg - LATERAL_BASELINE_TO_BODY_OFFSET_DEG)


def yaw_residual_deg(estimate_body_yaw_deg: float, reference_body_yaw_deg: float) -> float:
    return wrap180_deg(estimate_body_yaw_deg - reference_body_yaw_deg)


def circular_blend_deg(previous_deg: float | None, measurement_deg: float, alpha: float) -> float:
    if previous_deg is None:
        return wrap360_deg(measurement_deg)
    delta = wrap180_deg(measurement_deg - previous_deg)
    return wrap360_deg(previous_deg + alpha * delta)


def synthetic_yaw_frame_checks() -> dict[str, bool]:
    return {
        "body0_baseline_minus90": abs(wrap180_deg(body_yaw_to_lateral_baseline_heading_deg(0.0) - 270.0)) < 1e-9,
        "body90_baseline0": abs(wrap180_deg(body_yaw_to_lateral_baseline_heading_deg(90.0) - 0.0)) < 1e-9,
        "wrap_179_minus_minus179": abs(yaw_residual_deg(179.0, -179.0) + 2.0) < 1e-9,
        "wrap_minus179_minus_179": abs(yaw_residual_deg(-179.0, 179.0) - 2.0) < 1e-9,
    }
