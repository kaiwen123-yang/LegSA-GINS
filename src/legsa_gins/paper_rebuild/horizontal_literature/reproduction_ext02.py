"""Versioned single-baseline C-WLS with Algorithm-1 tangent peaks retained.

Only the tangent candidate branch changes relative to ``ext02_cwls``.
Observation/model types, Eq. (54) scoring, Eq. (75) half-down refinement,
sphere subproblems, tolerances and fail-closed complete-pool policy are reused.
The historical module and its module globals are never patched by this module.
This is the single-baseline branch, not a multi-antenna attitude implementation.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from . import ext02_cwls as _core


IMPLEMENTATION_ID = "EXT02_CWLS_TANGENT_PEAKS_V1"
DELTA_DELTA = _core.DELTA_DELTA
REFINEMENT_MAX_ITERATIONS = _core.REFINEMENT_MAX_ITERATIONS
REFINEMENT_TOL = _core.REFINEMENT_TOL
CWLSError = _core.CWLSError
CWLSGeometryError = _core.CWLSGeometryError
CWLSNumericalError = _core.CWLSNumericalError
SingleBaselineCWLSModel = _core.SingleBaselineCWLSModel
SphereCircle = _core.SphereCircle
CirclePairGeometry = _core.CirclePairGeometry
CandidatePool = _core.CandidatePool
CWLSSolution = _core.CWLSSolution
wrapped_objective = _core.wrapped_objective
round_half_down = _core.round_half_down
wrap_half_cycles = _core.wrap_half_cycles
adapt_metric_double_differences = _core.adapt_metric_double_differences

# Local bindings allow synthetic failure injection without modifying old globals.
_refine_candidate = _core._refine_candidate
_failed_candidate_diagnostic = _core._failed_candidate_diagnostic


def intersect_sphere_circles(
    first: SphereCircle, second: SphereCircle
) -> CirclePairGeometry:
    """Keep both permitted Algorithm-1 peaks for an old tangent outcome.

The old implementation returns the touching point immediately. Algorithm 1's
non-crossing branch independently admits each peak when ``abs(Delta)<0.05``;
the opposite peak may also qualify. Non-tangent and degenerate outcomes are
returned unchanged. The existing ``tangent`` kind remains API-compatible.
"""
    result = _core.intersect_sphere_circles(first, second)
    if result.kind != "tangent":
        return result
    cross = np.cross(first.normal, second.normal)
    v1 = cross / np.linalg.norm(cross)
    v2 = np.cross(v1, second.normal)
    v2 /= np.linalg.norm(v2)
    peaks = (
        second.center - second.radius * v2,
        second.center + second.radius * v2,
    )
    candidates = _core.deduplicate_directions_machine_precision(
        peak
        for peak, delta in zip(peaks, (result.delta_1, result.delta_2), strict=True)
        if abs(delta) < DELTA_DELTA
    )
    return CirclePairGeometry(
        "tangent", candidates, result.delta_1, result.delta_2, result.parallel_relation
    )


def generate_candidate_pool(model: SingleBaselineCWLSModel) -> CandidatePool:
    """Algorithm 1, with K equal to the entire unique corrected candidate pool."""
    circles = _core.build_search_circles(model)
    pair_results = []
    raw_directions = []
    for first, second in combinations(circles, 2):
        if first.observation_index == second.observation_index:
            continue
        geometry = intersect_sphere_circles(first, second)
        pair_results.append(geometry)
        raw_directions.extend(geometry.candidates)
    unique = _core.deduplicate_directions_machine_precision(raw_directions)
    if not unique:
        raise CWLSGeometryError(
            "Algorithm 1 produced no finite direction candidates",
            code="NO_CIRCLE_PAIR_CANDIDATE",
        )
    integer_counts = tuple(
        sum(circle.observation_index == row for circle in circles)
        for row in range(model.observation_count)
    )
    intersecting_kinds = {"two_intersections", "tangent", "point_intersection"}
    near_kinds = {"near_tangent", "point_near_tangent"}
    # Count the extra tangent peak as a near candidate while counting the pair
    # once as intersecting. No new scientific tolerance or dedup rule is added.
    near_count = sum(
        len(item.candidates) if item.kind in near_kinds
        else max(0, len(item.candidates) - 1) if item.kind == "tangent"
        else 0
        for item in pair_results
    )
    return CandidatePool(
        circles=circles,
        pair_geometries=tuple(pair_results),
        directions=unique,
        pair_count=len(pair_results),
        raw_candidate_count=len(raw_directions),
        phase_row_count=model.observation_count,
        integer_option_count_per_row=integer_counts,
        intersecting_pair_count=sum(x.kind in intersecting_kinds for x in pair_results),
        near_tangent_candidate_count=near_count,
        degenerate_pair_count=sum(
            x.parallel_relation is not None or x.kind.startswith("point_")
            for x in pair_results
        ),
    )


def solve_cwls(model: SingleBaselineCWLSModel) -> CWLSSolution:
    """Use the corrected pool with the unchanged Algorithm-2 core and result API.

The old solver has no candidate-generator argument. Only its short orchestration
is repeated here: all unique candidates are refined; any incomplete refinement
rejects the epoch; final ordering uses Eq. (54), not the Eq. (75) surrogate.
Both objectives remain present in each original ``CandidateDiagnostic``.
"""
    pool = generate_candidate_pool(model)
    cache: dict[tuple[int, ...], _core.SphereQuadraticSolution] = {}
    diagnostic_list = []
    for index, direction in enumerate(pool.directions):
        try:
            diagnostic = _refine_candidate(model, index, direction, cache)
        except CWLSNumericalError as exc:
            failure_code = (
                exc.code if exc.code in {"SPHERE_SOLVER_FAILURE", "NONFINITE_OBJECTIVE"}
                else "SPHERE_SOLVER_FAILURE"
            )
            diagnostic = _failed_candidate_diagnostic(model, index, direction, failure_code)
        diagnostic_list.append(diagnostic)
    diagnostics = tuple(diagnostic_list)
    converged = tuple(item for item in diagnostics if item.converged)
    if not converged:
        failures = sorted({x.failure_code for x in diagnostics if x.failure_code is not None})
        raise CWLSNumericalError(
            "ALL_REFINEMENTS_FAILED: " + (",".join(failures) if failures else "NONCONVERGENCE"),
            code="ALL_REFINEMENTS_FAILED",
            candidate_diagnostics=diagnostics,
            candidate_pool=pool,
        )
    incomplete = tuple(
        x for x in diagnostics
        if not x.converged or x.failure_code is not None
        or x.objective is None or not np.isfinite(x.objective)
    )
    if incomplete:
        terminal_code = (
            "SPHERE_SOLVER_FAILURE"
            if any(x.failure_code == "SPHERE_SOLVER_FAILURE" for x in incomplete)
            else "NUMERICAL_FAILURE"
        )
        failures = sorted({x.failure_code or x.convergence_state for x in incomplete})
        raise CWLSNumericalError(
            f"INCOMPLETE_CANDIDATE_REFINEMENT_POOL: {len(incomplete)}/{len(diagnostics)}; "
            + ",".join(failures),
            code=terminal_code,
            candidate_diagnostics=diagnostics,
            candidate_pool=pool,
        )
    selected = min(
        converged,
        key=lambda item: (
            float(item.objective),
            float(item.refined_direction[0]),
            float(item.refined_direction[1]),
            float(item.refined_direction[2]),
            item.integer_ambiguities,
            item.coarse_index,
        ),
    )
    return CWLSSolution(
        direction=selected.refined_direction,
        baseline_vector_m=_core._readonly_float_array(
            model.baseline_length_m * selected.refined_direction
        ),
        objective=float(selected.objective),
        integer_corrections=selected.integer_corrections,
        integer_ambiguities=selected.integer_ambiguities,
        selected_candidate_index=selected.coarse_index,
        exact_objective_tie_count=sum(x.objective == selected.objective for x in converged),
        circle_count=len(pool.circles),
        circle_pair_count=pool.pair_count,
        raw_candidate_count=pool.raw_candidate_count,
        candidate_count=len(pool.directions),
        phase_row_count=model.observation_count,
        integer_option_count_per_row=pool.integer_option_count_per_row,
        intersecting_pair_count=pool.intersecting_pair_count,
        near_tangent_candidate_count=pool.near_tangent_candidate_count,
        degenerate_pair_count=pool.degenerate_pair_count,
        diagnostics=diagnostics,
    )


solve_single_baseline_cwls = solve_cwls

__all__ = [
    "IMPLEMENTATION_ID", "DELTA_DELTA", "REFINEMENT_MAX_ITERATIONS", "REFINEMENT_TOL",
    "CWLSError", "CWLSGeometryError", "CWLSNumericalError", "SingleBaselineCWLSModel",
    "SphereCircle", "CirclePairGeometry", "CandidatePool", "CWLSSolution",
    "intersect_sphere_circles", "generate_candidate_pool", "solve_cwls",
    "solve_single_baseline_cwls", "wrapped_objective", "round_half_down",
    "wrap_half_cycles", "adapt_metric_double_differences",
]
