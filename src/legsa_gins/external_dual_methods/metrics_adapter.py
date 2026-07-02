"""Evaluation metric placeholders for Q2R2 external method outputs."""

from __future__ import annotations


def not_applicable_metric(reason: str) -> dict[str, str]:
    return {
        "horizontal_rmse_m": "not_applicable",
        "up_rmse_m": "not_applicable",
        "yaw_rmse_deg": "not_applicable",
        "reason": reason,
    }
