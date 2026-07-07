"""Constrained LAMBDA search helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .baseline_constraint import BaselineConstraint
from .lambda_solver import LambdaCandidate, solve_integer_least_squares


@dataclass(frozen=True)
class ConstrainedLambdaResult:
    fixed: tuple[int, ...] | None
    squared_norm: float | None
    ratio: float | None
    accepted_candidates: tuple[LambdaCandidate, ...]
    rejected_candidate_count: int
    constraint_passed: bool


def solve_constrained_lambda(
    float_ambiguity: Iterable[float],
    covariance: Iterable[Iterable[float]],
    *,
    baseline_from_integer: Callable[[tuple[int, ...]], tuple[float, float, float]],
    constraint: BaselineConstraint,
    search_radius: int = 3,
) -> ConstrainedLambdaResult:
    unconstrained = solve_integer_least_squares(float_ambiguity, covariance, search_radius=search_radius, max_candidates=512)
    accepted: list[LambdaCandidate] = []
    rejected = 0
    for candidate in unconstrained.candidates:
        if constraint.passes(baseline_from_integer(candidate.integers)):
            accepted.append(candidate)
        else:
            rejected += 1
    accepted.sort(key=lambda item: item.squared_norm)
    if not accepted:
        return ConstrainedLambdaResult(None, None, None, tuple(), rejected, False)
    ratio = None
    if len(accepted) > 1 and accepted[0].squared_norm > 0.0:
        ratio = accepted[1].squared_norm / accepted[0].squared_norm
    return ConstrainedLambdaResult(accepted[0].integers, accepted[0].squared_norm, ratio, tuple(accepted), rejected, True)
