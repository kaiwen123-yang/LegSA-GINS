"""Small LAMBDA-style integer candidate helpers."""

from __future__ import annotations

import math


def nearest_integer_candidates(values: list[float], *, width: int = 1) -> list[list[int]]:
    candidates = []
    for value in values:
        center = int(round(value))
        candidates.append(list(range(center - width, center + width + 1)))
    return candidates


def ratio_test(best_cost: float, second_cost: float, threshold: float = 3.0) -> bool:
    if best_cost <= 0.0:
        return True
    if not math.isfinite(best_cost) or not math.isfinite(second_cost):
        return False
    return second_cost / best_cost >= threshold
