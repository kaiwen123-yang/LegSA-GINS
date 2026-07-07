"""Small integer least-squares solver used by DA01 tests and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class LambdaCandidate:
    integers: tuple[int, ...]
    squared_norm: float


@dataclass(frozen=True)
class LambdaResult:
    fixed: tuple[int, ...]
    squared_norm: float
    ratio: float | None
    candidates: tuple[LambdaCandidate, ...]


def _candidate_ranges(float_ambiguity: np.ndarray, search_radius: int) -> Iterable[tuple[int, ...]]:
    centers = [int(round(value)) for value in float_ambiguity]
    ranges = [range(center - search_radius, center + search_radius + 1) for center in centers]
    return product(*ranges)


def solve_integer_least_squares(
    float_ambiguity: Iterable[float],
    covariance: Iterable[Iterable[float]],
    *,
    search_radius: int = 3,
    max_candidates: int = 32,
) -> LambdaResult:
    afloat = np.asarray(list(float_ambiguity), dtype=float)
    if afloat.ndim != 1 or afloat.size == 0:
        raise ValueError("float_ambiguity must be a non-empty vector")
    q = np.asarray(list(list(row) for row in covariance), dtype=float)
    if q.shape != (afloat.size, afloat.size):
        raise ValueError("covariance shape does not match ambiguity vector")
    q_inv = np.linalg.pinv(q)
    candidates: list[LambdaCandidate] = []
    for ints in _candidate_ranges(afloat, search_radius):
        diff = afloat - np.asarray(ints, dtype=float)
        norm = float(diff.T @ q_inv @ diff)
        candidates.append(LambdaCandidate(tuple(int(v) for v in ints), norm))
    candidates.sort(key=lambda item: item.squared_norm)
    kept = tuple(candidates[:max_candidates])
    if not kept:
        raise ValueError("no integer candidates generated")
    ratio = None
    if len(kept) > 1 and kept[0].squared_norm > 0.0:
        ratio = kept[1].squared_norm / kept[0].squared_norm
    return LambdaResult(kept[0].integers, kept[0].squared_norm, ratio, kept)
