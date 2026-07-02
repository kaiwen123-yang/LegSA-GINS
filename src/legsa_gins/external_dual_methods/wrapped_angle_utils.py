"""Wrap-safe angle helpers for yaw evaluation."""

from __future__ import annotations


def wrap360_deg(angle_deg: float) -> float:
    return angle_deg % 360.0


def wrap180_deg(angle_deg: float) -> float:
    return (angle_deg + 180.0) % 360.0 - 180.0


def yaw_error_deg(estimate_deg: float, reference_deg: float) -> float:
    return wrap180_deg(estimate_deg - reference_deg)
