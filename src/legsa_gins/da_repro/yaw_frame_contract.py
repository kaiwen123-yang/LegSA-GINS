"""Yaw-frame contract for lateral dual-antenna DA01 outputs."""

from __future__ import annotations

from typing import Any

from .common import wrap180, wrap360


def baseline_heading_from_enu(east_m: float, north_m: float) -> float:
    import math

    return wrap360(math.degrees(math.atan2(float(east_m), float(north_m))))


def body_yaw_from_lateral_baseline(baseline_heading_deg: float, *, offset_deg: float = 90.0) -> float:
    return wrap360(float(baseline_heading_deg) + float(offset_deg))


def yaw_residual_deg(estimate_deg: float, reference_deg: float) -> float:
    return wrap180(float(estimate_deg) - float(reference_deg))


def make_yaw_frame_contract(*, gnss_order: str = "GNSS2-GNSS1", offset_deg: float = 90.0) -> dict[str, Any]:
    return {
        "mounting": "lateral_dual_antenna",
        "gnss_order": gnss_order,
        "coordinate_frame": "ENU baseline vector, body yaw reported as degrees clockwise from north",
        "baseline_heading_is_body_yaw": False,
        "body_yaw_formula": "wrap360(baseline_heading_deg + lateral_offset_deg)",
        "lateral_offset_deg": offset_deg,
        "residual_policy": "wrap_safe_180_deg",
        "trace_rmse_selected_sign": False,
        "per_case_offset": False,
        "yaw_frame_contract_passed": gnss_order == "GNSS2-GNSS1" and offset_deg in (90.0, -90.0),
    }


def synthetic_contract_test() -> dict[str, Any]:
    heading = baseline_heading_from_enu(0.0, 1.0)
    body = body_yaw_from_lateral_baseline(heading, offset_deg=90.0)
    residual = yaw_residual_deg(1.0, 359.0)
    return {
        "baseline_north_heading_deg": heading,
        "body_yaw_with_plus90_deg": body,
        "wrap_safe_residual_1_minus_359_deg": residual,
        "passed": heading == 0.0 and body == 90.0 and residual == 2.0,
    }
