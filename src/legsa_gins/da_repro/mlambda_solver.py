"""MLAMBDA-style sorted integer candidate helper."""

from __future__ import annotations


def sorted_integer_candidates(value: float, *, radius: int = 2) -> list[tuple[int, float]]:
    center = int(round(value))
    out = [(candidate, (value - candidate) ** 2) for candidate in range(center - radius, center + radius + 1)]
    return sorted(out, key=lambda item: item[1])
