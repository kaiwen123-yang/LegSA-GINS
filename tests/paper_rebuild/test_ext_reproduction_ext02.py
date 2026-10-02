"""Synthetic-only checks for the versioned Algorithm-1 tangent correction."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from inspect import signature
from itertools import product
import math

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature import ext02_cwls as old
from legsa_gins.paper_rebuild.horizontal_literature import reproduction_ext02 as new


def _full_q(rows: int) -> np.ndarray:
    sigma = np.r_[np.full(rows, 0.01), np.full(rows, 0.04)]
    correlation = 0.94 * np.eye(2 * rows) + 0.06 * np.ones((2 * rows, 2 * rows))
    return sigma[:, None] * correlation * sigma[None, :]


def _noiseless_model(rows: int = 4):
    rng = np.random.default_rng(600 + rows)
    design = rng.normal(size=(rows, 3))
    design /= np.linalg.norm(design, axis=1)[:, None]
    design *= 2.0
    direction = np.array([0.3, -0.4, math.sqrt(0.75)])
    length = 0.35
    prediction = length * design @ direction
    ambiguities = np.arange(rows) % 3 - 1
    return (
        new.SingleBaselineCWLSModel(
            prediction + ambiguities, prediction, design, _full_q(rows), length
        ),
        direction,
        ambiguities,
    )


def _independent_cost(model, direction):
    prediction = model.baseline_length_m * model.design_cycles_per_m @ direction
    raw = model.phase_cycles - prediction
    phase = raw - np.array([math.ceil(float(x) - 0.5) for x in raw])
    residual = np.r_[phase, model.code_cycles - prediction]
    return float(residual @ np.linalg.solve(model.covariance_phase_code_cycles2, residual))


@pytest.mark.parametrize("offset", [0.02, -0.02])
def test_tangent_keeps_both_independently_qualified_peaks(offset):
    z = math.sqrt(1.0 - offset * offset)
    first = new.SphereCircle([1.0, 0.0, 0.0], offset)
    second = new.SphereCircle([0.0, 0.0, 1.0], z)
    legacy = old.intersect_sphere_circles(first, second)
    corrected = new.intersect_sphere_circles(first, second)
    assert legacy.kind == corrected.kind == "tangent"
    assert len(legacy.candidates) == 1
    assert len(corrected.candidates) == 2
    assert sorted(abs(x) for x in (corrected.delta_1, corrected.delta_2)) == pytest.approx(
        [0.0, 0.04], abs=2e-14
    )
    assert np.allclose(corrected.candidates, [[-abs(offset), 0.0, z], [abs(offset), 0.0, z]],
                       atol=2e-14, rtol=0.0)
    assert all(abs(x) < new.DELTA_DELTA for x in (corrected.delta_1, corrected.delta_2))


def test_tangent_does_not_keep_nonqualifying_opposite_peak():
    first = new.SphereCircle([1, 0, 0], 0.04)
    second = new.SphereCircle([0, 0, 1], math.sqrt(1 - 0.04**2))
    result = new.intersect_sphere_circles(first, second)
    assert result.kind == "tangent"
    assert len(result.candidates) == 1
    assert result.candidates[0][0] == pytest.approx(0.04, abs=2e-14)
    assert max(abs(result.delta_1), abs(result.delta_2)) > new.DELTA_DELTA


@pytest.mark.parametrize("normals_offsets", [
    ([1, 0, 0], 0.0, [0, 0, 1], 0.0),
    ([1, 0, 0], 0.8, [0, 0, 1], 0.8),
    ([1, 0, 0], 0.1, [0, 0, 1], math.sqrt(1 - 0.08**2)),
    ([1, 0, 0], 1.0, [0, 0, 1], 0.0),
    ([1, 0, 0], 0.2, [1, 0, 0], 0.2),
    ([1, 0, 0], 0.2, [-1, 0, 0], -0.2),
    ([1, 0, 0], 0.2, [1, 0, 0], 0.3),
])
def test_all_other_geometry_branches_unchanged(normals_offsets):
    n1, c1, n2, c2 = normals_offsets
    first, second = new.SphereCircle(n1, c1), new.SphereCircle(n2, c2)
    a, b = old.intersect_sphere_circles(first, second), new.intersect_sphere_circles(first, second)
    assert a.kind != "tangent"
    assert (a.kind, a.delta_1, a.delta_2, a.parallel_relation) == (
        b.kind, b.delta_1, b.delta_2, b.parallel_relation
    )
    assert len(a.candidates) == len(b.candidates)
    assert all(np.array_equal(x, y) for x, y in zip(a.candidates, b.candidates, strict=True))


def test_corrected_pool_includes_opposite_tangent_peak_and_all_unique_k():
    z = math.sqrt(1 - 0.02**2)
    model = new.SingleBaselineCWLSModel(
        [0.02, z], [0.02, z], [[1, 0, 0], [0, 0, 1]], _full_q(2), 1.0
    )
    legacy = old.generate_candidate_pool(model)
    corrected = new.generate_candidate_pool(model)
    opposite = np.array([-0.02, 0, z])
    assert not any(np.allclose(x, opposite, atol=2e-14, rtol=0) for x in legacy.directions)
    assert any(np.allclose(x, opposite, atol=2e-14, rtol=0) for x in corrected.directions)
    assert corrected.raw_candidate_count == legacy.raw_candidate_count + 1
    assert corrected.near_tangent_candidate_count == legacy.near_tangent_candidate_count + 1
    solution = new.solve_cwls(model)
    assert solution.candidate_count == len(corrected.directions) == len(solution.diagnostics)
    assert [x.coarse_index for x in solution.diagnostics] == list(range(solution.candidate_count))
    assert all(x.converged for x in solution.diagnostics)


@pytest.mark.parametrize("rows", [3, 4, 6])
def test_noiseless_full_q_recovery_legacy_equivalence_and_input_immutability(rows):
    model, truth, ambiguities = _noiseless_model(rows)
    before = [x.tobytes() for x in (model.phase_cycles, model.code_cycles,
              model.design_cycles_per_m, model.covariance_phase_code_cycles2)]
    pool = new.generate_candidate_pool(model)
    assert all(x.kind != "tangent" for x in pool.pair_geometries)
    result = new.solve_cwls(model)
    previous = old.solve_single_baseline_cwls(model)
    assert isinstance(result, old.CWLSSolution)
    assert np.allclose(result.direction, truth, atol=5e-13, rtol=0)
    assert result.integer_ambiguities == tuple(ambiguities)
    assert result.objective < 1e-20
    assert np.array_equal(result.direction, previous.direction)
    assert result.objective == previous.objective
    assert result.candidate_count == previous.candidate_count
    assert before == [x.tobytes() for x in (model.phase_cycles, model.code_cycles,
                      model.design_cycles_per_m, model.covariance_phase_code_cycles2)]


@pytest.mark.parametrize("noise_scale", [0.0, 0.4, 1.0])
def test_exhaustive_integer_oracle_with_full_correlated_q_and_analytic_sphere(noise_scale):
    # Full precision is correlated, but D'P D = 4*a^2 I. Every fixed-integer
    # sphere minimum therefore has an independent closed form, no core solver.
    a = 0.7
    c = np.array([[0.1, 0.04, -0.03], [0.04, -0.1, 0.02], [-0.03, 0.02, 0.07]])
    b = np.array([[0.03, -0.02, 0.01], [-0.02, 0.02, 0.01], [0.01, 0.01, -0.02]])
    precision = np.block([[2*np.eye(3) + c, b], [b.T, 2*np.eye(3) - c - 2*b]])
    q = np.linalg.inv(precision)
    assert np.min(np.linalg.eigvalsh(q)) > 0
    assert np.count_nonzero(np.abs(q - np.diag(np.diag(q))) > 1e-8) > 12
    true_direction = np.array([0.3, -0.4, math.sqrt(0.75)])
    prediction = a * true_direction
    phase = prediction + [1, -1, 0] + noise_scale*np.array([0.009, -0.006, 0.003])
    code = prediction + noise_scale*np.array([0.007, 0.004, -0.008])
    model = new.SingleBaselineCWLSModel(phase, code, a*np.eye(3), q, 1.0)
    design = np.vstack([a*np.eye(3), a*np.eye(3)])
    assert np.allclose(design.T @ np.linalg.solve(q, design), 4*a*a*np.eye(3), atol=1e-15)
    ranges = [range(math.ceil(x-a-0.5), math.floor(x+a+0.5)+1) for x in phase]
    lower_bounds = []
    for integers in product(*ranges):
        y = np.r_[phase - integers, code]
        linear = design.T @ np.linalg.solve(q, y)
        direction = linear / np.linalg.norm(linear)
        bound = float(y @ np.linalg.solve(q, y) + 4*a*a - 2*np.linalg.norm(linear))
        lower_bounds.append((bound, tuple(integers), direction))
    assert len(lower_bounds) >= 8
    bound, integers, direction = min(lower_bounds, key=lambda row: row[0])
    # The smallest relaxed branch minimum is feasible for its wrapped cell;
    # hence this lower bound is attained and globally certifies THIS fixture.
    actual_cell = tuple(math.ceil(float(x)-0.5) for x in phase - a*direction)
    assert actual_cell == integers
    oracle = _independent_cost(model, direction)
    assert oracle == pytest.approx(bound, abs=2e-14)
    solution = new.solve_cwls(model)
    assert solution.objective == pytest.approx(oracle, abs=2e-13, rel=2e-12)
    assert np.allclose(solution.direction, direction, atol=2e-12, rtol=0)
    assert solution.integer_ambiguities == integers
    assert solution.objective == pytest.approx(_independent_cost(model, solution.direction), abs=2e-13)


@pytest.mark.parametrize("value,expected", [(-1.5, -2), (-0.5, -1), (0.5, 0), (1.5, 1)])
def test_paper_half_down_ties_preserved_and_eq75_residual_sign_is_distinct(value, expected):
    assert new.round_half_down is old.round_half_down
    assert new.wrap_half_cycles is old.wrap_half_cycles
    assert new.round_half_down(value) == expected
    assert new.wrap_half_cycles(value) == 0.5
    assert value + new.round_half_down(-value) == -0.5


@pytest.mark.parametrize("tie", [-1.5, -0.5, 0.5, 1.5])
@pytest.mark.parametrize("toward", [-np.inf, np.inf])
def test_half_tie_nextafter_preserves_existing_binary64_expression(tie, toward):
    adjacent = np.nextafter(tie, toward)
    expected = int(np.ceil(adjacent - np.float64(0.5)))
    assert new.round_half_down(adjacent) == old.round_half_down(adjacent) == expected
    assert new.wrap_half_cycles(adjacent) == adjacent - expected


def test_existing_binary64_shift_can_erase_one_half_tie_neighbor():
    adjacent = np.nextafter(-0.5, np.inf)
    exact = math.ceil(Fraction.from_float(float(adjacent)) - Fraction(1, 2))
    assert exact == 0
    assert old.round_half_down(adjacent) == new.round_half_down(adjacent) == -1
    # This is an inherited rounding limitation, NOT part of the tangent fix.


def test_correlated_q_half_tie_has_distinct_wrapped_and_eq75_objectives(monkeypatch):
    q = np.eye(4)
    q[0, 2] = q[2, 0] = 0.4
    model = new.SingleBaselineCWLSModel([0.5, 0], [0.2, 0], [[0, 1, 0], [0, 0, 1]], q, 1.0)
    direction = np.array([1.0, 0.0, 0.0])
    correction = old._integer_corrections(model, direction)
    assert tuple(correction) == (-1, 0)
    wrapped = np.array([0.5, 0, 0.2, 0])
    surrogate = np.array([-0.5, 0, 0.2, 0])
    wrapped_cost = float(wrapped @ np.linalg.solve(q, wrapped))
    surrogate_cost = float(surrogate @ np.linalg.solve(q, surrogate))
    assert wrapped_cost != surrogate_cost
    assert new.wrapped_objective(model, direction) == pytest.approx(wrapped_cost)
    # A deliberately fixed synthetic subproblem result isolates bookkeeping at
    # the tie. It is NOT a claim that this direction solves this model.
    stub = old.solve_unit_sphere_quadratic(np.zeros((3, 3)), direction)
    monkeypatch.setattr(old, "_fixed_integer_sphere_solution", lambda *_: stub)
    diagnostic = new._refine_candidate(model, 0, direction, {})
    assert diagnostic.converged
    assert diagnostic.objective == pytest.approx(wrapped_cost)
    assert diagnostic.refined_unwrapped_objective == pytest.approx(surrogate_cost)


def test_unchanged_api_and_engineering_defaults():
    assert signature(new.solve_cwls) == signature(old.solve_single_baseline_cwls)
    assert new.solve_cwls is new.solve_single_baseline_cwls
    assert new.SingleBaselineCWLSModel is old.SingleBaselineCWLSModel
    assert new.CWLSSolution is old.CWLSSolution
    assert new.DELTA_DELTA == 0.05
    assert new.REFINEMENT_MAX_ITERATIONS == 20
    assert new.REFINEMENT_TOL == 1e-10


@pytest.mark.parametrize("bad_input", ["nonfinite", "non_spd", "empty_interval", "parallel"])
def test_negative_inputs_fail_closed_without_fabricated_solution(bad_input):
    phase = np.zeros(2)
    design = np.array([[1., 0, 0], [0, 1., 0]])
    q = np.eye(4)
    if bad_input == "nonfinite":
        phase[0] = np.nan
    elif bad_input == "non_spd":
        q[0, 0] = -1
    elif bad_input == "empty_interval":
        phase[:] = 0.5
        design *= 0.01
    else:
        design[1] = design[0]
        # Only ambiguity 0 is feasible, so the coincident circles are not the
        # +/-1 point circles that can legitimately supply finite candidates.
        design *= 0.2
    with pytest.raises(new.CWLSError):
        model = new.SingleBaselineCWLSModel(phase, np.zeros(2), design, q, 1.0)
        new.solve_cwls(model)


@pytest.mark.parametrize("fail_all", [False, True])
def test_candidate_failure_does_not_skip_pool_and_cannot_return_partial_success(monkeypatch, fail_all):
    model, _, _ = _noiseless_model()
    expected = len(new.generate_candidate_pool(model).directions)
    original = new._refine_candidate
    visited = []

    def injected(model, index, direction, cache):
        visited.append(index)
        if fail_all or index == 0:
            raise new.CWLSNumericalError("synthetic injected failure", code="SPHERE_SOLVER_FAILURE")
        return original(model, index, direction, cache)

    monkeypatch.setattr(new, "_refine_candidate", injected)
    with pytest.raises(new.CWLSNumericalError) as caught:
        new.solve_cwls(model)
    assert visited == list(range(expected))
    assert len(caught.value.candidate_diagnostics) == expected
    failed = [x for x in caught.value.candidate_diagnostics if x.failure_code]
    assert len(failed) == (expected if fail_all else 1)
    assert all(not x.converged and x.objective is None for x in failed)
    assert caught.value.code == ("ALL_REFINEMENTS_FAILED" if fail_all else "SPHERE_SOLVER_FAILURE")


def test_twenty_iteration_exhaustion_is_visible_and_rejects_entire_pool(monkeypatch):
    model = new.SingleBaselineCWLSModel([0, 0], [0, 0], [[1, 0, 0], [0, 1, 0]], np.eye(4), 1.0)
    stub = old.solve_unit_sphere_quadratic(np.zeros((3, 3)), np.array([1., 0, 0]))

    def alternating(_model, corrections):
        direction = np.array([-1., 0, 0]) if corrections[0] >= 0 else np.array([1., 0, 0])
        return replace(stub, direction=direction)

    # Deliberate synthetic subproblem cycling tests bounded-resource behavior;
    # it does not assert these injected subproblems are mathematical solutions.
    monkeypatch.setattr(old, "_fixed_integer_sphere_solution", alternating)
    with pytest.raises(new.CWLSNumericalError) as caught:
        new.solve_cwls(model)
    assert caught.value.code == "ALL_REFINEMENTS_FAILED"
    diagnostics = caught.value.candidate_diagnostics
    assert len(diagnostics) == len(caught.value.candidate_pool.directions)
    assert all(x.iteration_count == 20 and len(x.iterations) == 20 for x in diagnostics)
    assert all(not x.converged and not x.integer_vector_stable for x in diagnostics)
    assert all(x.convergence_state.startswith("MAX_ITERATIONS") for x in diagnostics)
    assert all(x.objective is not None for x in diagnostics)
