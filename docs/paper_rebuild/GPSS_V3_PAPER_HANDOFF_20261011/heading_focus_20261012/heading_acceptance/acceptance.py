"""Prespecified engineering ratio gate applied to saved native evidence only.

No reference, yaw error or other method output is consumed by this module.
It preserves the original solution and only adds an explicit acceptance flag.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class Decision:
    accepted: bool
    acceptance_state: str
    best_cost: float | None = None
    second_cost: float | None = None
    ratio: float | None = None
    distinct_hypotheses: int = 0
    original_candidate_count: int = 0

    def row(self):
        return asdict(self)


def ratio_gate(best: float, second: float, threshold: float = 3.0) -> Decision:
    if not math.isfinite(threshold) or threshold <= 1:
        raise ValueError("threshold must be finite and > 1")
    if not all(math.isfinite(x) and x >= 0 for x in (best, second)):
        return Decision(False, "INVALID_COST", best, second)
    if second < best:
        return Decision(False, "UNSORTED_COST", best, second)
    if best == 0:
        return Decision(False, "ZERO_BEST_COST", best, second)
    ratio = second / best
    if not math.isfinite(ratio):
        return Decision(False, "NONFINITE_RATIO", best, second)
    return Decision(ratio >= threshold,
                    "ACCEPTED_RATIO3" if ratio >= threshold else "REJECTED_RATIO",
                    best, second, ratio)


def _with_counts(d: Decision, distinct: int, total: int) -> Decision:
    return Decision(d.accepted, d.acceptance_state, d.best_cost,
                    d.second_cost, d.ratio, distinct, total)


def decide(record: dict, threshold: float = 3.0) -> Decision:
    if not record.get("valid"):
        return Decision(False, "NATIVE_INVALID")
    s = record.get("solver") or {}
    method = record["method"]
    if method == "EXT01":
        if not (record.get("search_complete") and s.get("global_optimum_certified")):
            return Decision(False, "NO_GLOBAL_SEARCH_CERTIFICATE")
        first, second = s.get("best"), s.get("second")
        if first is None or second is None:
            return Decision(False, "NO_SECOND_DISTINCT_HYPOTHESIS",
                            distinct_hypotheses=int(first is not None))
        if tuple(first["ambiguity"]) == tuple(second["ambiguity"]):
            return Decision(False, "DUPLICATE_INTEGER_HYPOTHESES", distinct_hypotheses=1)
        return _with_counts(ratio_gate(float(first["objective"]),
                                      float(second["objective"]), threshold), 2, 2)
    if method != "EXT02":
        raise ValueError(f"unsupported method {method}")
    pool = s.get("diagnostics") or []
    if len(pool) != s.get("candidate_count") or not pool or not record.get("search_complete"):
        return Decision(False, "INCOMPLETE_CANDIDATE_POOL", original_candidate_count=len(pool))
    unique = {}
    for d in pool:
        if not d.get("converged") or d.get("failure_code") or not d.get("integer_vector_stable"):
            return Decision(False, "INCOMPLETE_CANDIDATE_POOL", original_candidate_count=len(pool))
        cost = float(d["objective"])
        if not math.isfinite(cost) or cost < 0:
            return Decision(False, "INVALID_COST", original_candidate_count=len(pool))
        integers = tuple(d["integer_ambiguities"])
        unique[integers] = min(unique.get(integers, math.inf), cost)
    costs = sorted(unique.values())
    if len(costs) < 2:
        return Decision(False, "NO_SECOND_DISTINCT_HYPOTHESIS",
                        best_cost=costs[0] if costs else None,
                        distinct_hypotheses=len(costs), original_candidate_count=len(pool))
    # The extension must assess the already selected estimate, not select another.
    selected = tuple(s["integer_ambiguities"])
    if selected not in unique or not math.isclose(unique[selected], costs[0], rel_tol=1e-8, abs_tol=1e-9):
        return Decision(False, "SELECTED_SOLUTION_NOT_BEST", distinct_hypotheses=len(costs),
                        original_candidate_count=len(pool))
    if not math.isclose(float(s["objective"]), costs[0], rel_tol=1e-8, abs_tol=1e-9):
        return Decision(False, "SELECTED_OBJECTIVE_MISMATCH", distinct_hypotheses=len(costs),
                        original_candidate_count=len(pool))
    return _with_counts(ratio_gate(costs[0], costs[1], threshold), len(costs), len(pool))
