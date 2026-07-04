"""Baseline-length constraints for single-baseline attitude methods."""

from __future__ import annotations

import math


def project_horizontal_to_length(e_m: float, n_m: float, target_length_m: float) -> tuple[float, float]:
    length = math.hypot(e_m, n_m)
    if length <= 1e-12 or target_length_m <= 0.0:
        return e_m, n_m
    scale = target_length_m / length
    return e_m * scale, n_m * scale


def median_length(lengths: list[float]) -> float:
    clean = sorted(value for value in lengths if math.isfinite(value) and value > 0.0)
    if not clean:
        return 0.0
    mid = len(clean) // 2
    return clean[mid] if len(clean) % 2 else 0.5 * (clean[mid - 1] + clean[mid])
