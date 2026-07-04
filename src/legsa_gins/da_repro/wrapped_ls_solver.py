"""Wrapped least-squares helpers for yaw sequences."""

from __future__ import annotations

from .yaw_frame_contract import circular_mean_deg, yaw_error_deg


def wrapped_window_solution(values: list[float], weights: list[float] | None = None) -> float:
    return circular_mean_deg(values, weights)


def wrapped_residual_deg(value: float, reference: float) -> float:
    return yaw_error_deg(value, reference)
