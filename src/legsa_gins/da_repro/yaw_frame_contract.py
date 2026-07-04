"""Yaw-frame contract for lateral dual-antenna baseline estimates."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class YawFrameContract:
    baseline_vector_convention: str
    body_yaw_offset_deg: float
    enu_baseline_input: bool = True

    def body_yaw_deg(self, baseline_e_m: float, baseline_n_m: float) -> float:
        heading = baseline_heading_deg(baseline_e_m, baseline_n_m)
        return wrap360_deg(heading + self.body_yaw_offset_deg)


GNSS2_TO_GNSS1_RIGHT_CONTRACT = YawFrameContract(
    baseline_vector_convention="GNSS2_to_GNSS1_right_lateral_baseline",
    body_yaw_offset_deg=-90.0,
)

GNSS1_TO_GNSS2_LEFT_CONTRACT = YawFrameContract(
    baseline_vector_convention="GNSS1_to_GNSS2_left_lateral_baseline",
    body_yaw_offset_deg=90.0,
)


def wrap360_deg(value: float) -> float:
    out = value % 360.0
    return out + 360.0 if out < 0.0 else out


def wrap180_deg(value: float) -> float:
    out = (value + 180.0) % 360.0 - 180.0
    return 180.0 if out == -180.0 else out


def yaw_error_deg(estimate_deg: float, reference_deg: float) -> float:
    return wrap180_deg(estimate_deg - reference_deg)


def baseline_heading_deg(baseline_e_m: float, baseline_n_m: float) -> float:
    return wrap360_deg(math.degrees(math.atan2(baseline_e_m, baseline_n_m)))


def circular_mean_deg(values: list[float], weights: list[float] | None = None) -> float:
    if not values:
        return math.nan
    if weights is None:
        weights = [1.0] * len(values)
    x = 0.0
    y = 0.0
    for value, weight in zip(values, weights):
        rad = math.radians(value)
        x += math.cos(rad) * weight
        y += math.sin(rad) * weight
    if abs(x) < 1e-15 and abs(y) < 1e-15:
        return wrap360_deg(values[-1])
    return wrap360_deg(math.degrees(math.atan2(y, x)))


def synthetic_yaw_frame_checks() -> list[dict[str, str]]:
    checks = []
    for body_yaw, right_heading in ((0.0, 90.0), (90.0, 180.0)):
        got = wrap360_deg(right_heading - 90.0)
        checks.append(
            {
                "case": f"body_{body_yaw:.0f}_right_baseline",
                "expected_body_yaw_deg": f"{body_yaw:.6f}",
                "computed_body_yaw_deg": f"{got:.6f}",
                "passed": str(abs(wrap180_deg(got - body_yaw)) < 1e-9).lower(),
            }
        )
    err = yaw_error_deg(179.0, -179.0)
    checks.append(
        {
            "case": "wrap_residual_179_minus_minus179",
            "expected_error_abs_deg": "2.000000",
            "computed_error_deg": f"{err:.6f}",
            "passed": str(abs(abs(err) - 2.0) < 1e-9).lower(),
        }
    )
    return checks
