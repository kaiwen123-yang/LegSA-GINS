"""Yaw-aware smoothness helpers for N8A2.

中文说明：这里修正 smoothness yaw residual 的环绕约定，不删除 smoothness 因子。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_angle_utils import normalize_deg_0_360, unwrap_series_deg
from legsa_gins.fgo.fgo_linear_solver import moving_average
from legsa_gins.fgo.fgo_yaw_residuals import yaw_smoothness_residual_deg


def smooth_yaw_series_deg(values: list[float], *, window: int = 3, alpha: float = 1.0, output_0_360: bool = True) -> list[float]:
    if not values:
        return []
    unwrapped = unwrap_series_deg([float(value) for value in values])
    averaged = moving_average(unwrapped, window=window)
    blended = [raw + alpha * (avg - raw) for raw, avg in zip(unwrapped, averaged)]
    if output_0_360:
        return [normalize_deg_0_360(value) for value in blended]
    return blended


def yaw_smoothness_residual_series(values: list[float], *, expected_delta_yaw_deg: float = 0.0) -> list[float]:
    return [
        yaw_smoothness_residual_deg(prev, nxt, expected_delta_yaw_deg)
        for prev, nxt in zip(values, values[1:])
    ]


def build_yaw_smoothness_fix_report() -> dict[str, Any]:
    raw = [359.0, 1.0, 2.0]
    fixed = smooth_yaw_series_deg(raw)
    residuals = yaw_smoothness_residual_series(raw)
    return {
        "stage": "N8A2_fgo_yaw_convention_fix",
        "smoothness_factor_deleted": False,
        "smoothness_yaw_uses_shortest_angle": True,
        "toy_yaw_input_deg": raw,
        "toy_smoothed_yaw_deg": fixed,
        "toy_smoothness_residual_deg": residuals[0] if residuals else None,
        "toy_large_spike_absent": all(abs(value) < 10.0 for value in residuals),
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_yaw_correction": False,
        "paper_performance_claim": False,
    }
