"""Evaluation helpers for yaw-only external dual-antenna outputs."""

from __future__ import annotations

import math

from .method_runner import EpochEstimate


def yaw_metrics(estimates: list[EpochEstimate]) -> dict[str, str]:
    errors = [item.yaw_error_deg for item in estimates if item.yaw_error_deg is not None]
    valid_count = sum(1 for item in estimates if item.valid_measurement)
    if not errors:
        return {"epoch_count": str(len(estimates)), "valid_measurement_count": str(valid_count), "yaw_rmse_deg": "not_available", "yaw_mae_deg": "not_available", "horizontal_rmse_m": "not_applicable", "up_rmse_m": "not_applicable"}
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    mae = sum(abs(error) for error in errors) / len(errors)
    return {"epoch_count": str(len(estimates)), "valid_measurement_count": str(valid_count), "yaw_rmse_deg": f"{rmse:.6f}", "yaw_mae_deg": f"{mae:.6f}", "horizontal_rmse_m": "not_applicable", "up_rmse_m": "not_applicable"}
