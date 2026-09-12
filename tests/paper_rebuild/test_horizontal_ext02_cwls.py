"""Deterministic mathematical tests for the clean-room EXT02 C-WLS core."""

from __future__ import annotations

from dataclasses import replace
import math

import numpy as np
import pytest

import legsa_gins.paper_rebuild.horizontal_literature.ext02_cwls as ext02
from legsa_gins.paper_rebuild.horizontal_literature.ext02_cwls import (
    DELTA_DELTA,
    REFINEMENT_MAX_ITERATIONS,
    REFINEMENT_TOL,
    CWLSGeometryError,
    CWLSNumericalError,
    CWLSError,
    SingleBaselineCWLSModel,
    SphereCircle,
    adapt_metric_double_differences,
    build_double_difference_design,
    build_search_circles,
    deduplicate_directions_machine_precision,
    generate_candidate_pool,
    integer_ambiguity_interval,
    intersect_sphere_circles,
    round_half_down,
    solve_single_baseline_cwls,
    solve_unit_sphere_quadratic,
    stack_phase_code,
    wrap_half_cycles,
    wrapped_objective,
)


GPS_L1_WAVELENGTH_M = 0.190293672798365
DENSE_ORACLE_POINT_COUNT = 200_000
DENSE_ORACLE_MATERIAL_TOL = 1.0e-8


def _oracle_round_half_down(values: np.ndarray) -> np.ndarray:
    # Deliberately independent from the production helper and vectorized path.
    return np.array([math.ceil(float(value) - 0.5) for value in values], dtype=np.int64)


def _oracle_wrapped_objective(
    model: SingleBaselineCWLSModel, direction: np.ndarray
) -> float:
    direction = np.asarray(direction, dtype=float)
    direction = direction / np.linalg.norm(direction)
    prediction = model.baseline_length_m * model.design_cycles_per_m.dot(direction)
    raw_phase = model.phase_cycles - prediction
    phase_residual = raw_phase - _oracle_round_half_down(raw_phase)
    residual = np.r_[phase_residual, model.code_cycles - prediction]
    weighted = np.linalg.solve(model.covariance_phase_code_cycles2, residual)
    return float(residual.dot(weighted))


def _dense_fibonacci_wrapped_objective_minimum(
    model: SingleBaselineCWLSModel,
) -> float:
    """Independent dense full-sphere oracle; no production objective helper."""

    index = np.arange(DENSE_ORACLE_POINT_COUNT, dtype=np.float64) + 0.5
    z = 1.0 - 2.0 * index / DENSE_ORACLE_POINT_COUNT
    radial = np.sqrt(1.0 - z**2)
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    azimuth = golden_angle * index
    directions = np.column_stack(
        (radial * np.cos(azimuth), radial * np.sin(azimuth), z)
    )
    prediction = model.baseline_length_m * directions.dot(
        model.design_cycles_per_m.T
    )
    raw_phase = model.phase_cycles[None, :] - prediction
    # Independently spell out ceil(x - 0.5), rather than calling production wrap.
    phase_residual = raw_phase - np.ceil(raw_phase - 0.5)
    residual = np.concatenate(
        (phase_residual, model.code_cycles[None, :] - prediction), axis=1
    )
    precision = np.linalg.solve(
        model.covariance_phase_code_cycles2,
        np.eye(2 * model.observation_count),
    )
    objective = np.einsum(
        "ni,ij,nj->n", residual, precision, residual, optimize=True
    )
    return float(np.min(objective))


def _full_covariance(phase_sigma: float, code_sigma: float, rows: int) -> np.ndarray:
    standard_deviation = np.r_[
        np.full(rows, phase_sigma), np.full(rows, code_sigma)
    ]
    correlation = 0.94 * np.eye(2 * rows) + 0.06 * np.ones((2 * rows, 2 * rows))
    return standard_deviation[:, None] * correlation * standard_deviation[None, :]


def _synthetic_model(
    satellite_count: int,
    *,
    seed: int,
    pivot_index: int,
    phase_bias_cycles: float = 0.0,
    add_low_noise: bool = True,
) -> tuple[SingleBaselineCWLSModel, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    los = rng.normal(size=(satellite_count, 3))
    los /= np.linalg.norm(los, axis=1)[:, None]
    design = build_double_difference_design(los, pivot_index, GPS_L1_WAVELENGTH_M)
    true_direction = rng.normal(size=3)
    true_direction /= np.linalg.norm(true_direction)
    baseline_length = 0.35
    prediction = baseline_length * design.design_cycles_per_m.dot(true_direction)
    ambiguities = rng.integers(-3, 4, size=satellite_count - 1)
    covariance = _full_covariance(0.0015, 0.025, satellite_count - 1)
    if add_low_noise:
        noise = rng.multivariate_normal(
            np.zeros(2 * (satellite_count - 1)), covariance
        ) * 0.25
    else:
        noise = np.zeros(2 * (satellite_count - 1))
    phase = prediction + ambiguities + phase_bias_cycles + noise[: satellite_count - 1]
    code = prediction + noise[satellite_count - 1 :]
    model = SingleBaselineCWLSModel(
        phase,
        code,
        design.design_cycles_per_m,
        covariance,
        baseline_length,
    )
    return model, true_direction, ambiguities


def test_special_rounding_and_wrap_cover_all_half_integer_and_neighbor_cases():
    half_integers = np.arange(-6.5, 7.0, 1.0)
    expected_round = np.arange(-7, 7, dtype=np.int64)
    assert np.array_equal(round_half_down(half_integers), expected_round)
    assert np.array_equal(wrap_half_cycles(half_integers), np.full(14, 0.5))

    integers = np.arange(-7.0, 8.0)
    assert np.array_equal(round_half_down(integers), integers.astype(np.int64))
    assert np.array_equal(wrap_half_cycles(integers), np.zeros(integers.size))

    neighbors = np.array(
        [
            np.nextafter(-0.5, -np.inf),
            -0.5,
            np.nextafter(-0.5, np.inf),
            np.nextafter(0.5, -np.inf),
            0.5,
            np.nextafter(0.5, np.inf),
        ]
    )
    wrapped = np.asarray(wrap_half_cycles(neighbors))
    assert np.all(wrapped > -0.5)
    assert np.all(wrapped <= 0.5)
    assert wrapped[1] == 0.5
    assert wrapped[4] == 0.5
    assert round_half_down(2.5) == 2
    assert wrap_half_cycles(-3.5) == 0.5


def test_six_human_rounding_and_wrap_values_are_literal_and_exact():
    values = (0.5, -0.5, 1.5, -1.5, 0.5000000001, 0.4999999999)
    expected_round = (0, -1, 1, -2, 1, 0)
    expected_wrap = (
        0.5,
        0.5,
        0.5,
        0.5,
        0.5000000001 - 1.0,
        0.4999999999,
    )
    for value, rounded, wrapped in zip(
        values, expected_round, expected_wrap, strict=True
    ):
        assert round_half_down(value) == rounded
        assert wrap_half_cycles(value) == wrapped


def test_stack_phase_code_has_one_explicit_order_and_rejects_shape_mismatch():
    assert np.array_equal(stack_phase_code([1.0, 2.0], [3.0, 4.0]), [1, 2, 3, 4])
    with pytest.raises(CWLSError, match="equal-length"):
        stack_phase_code([1.0], [2.0, 3.0])


def test_equations_5_to_8_design_units_pivot_order_and_sign_are_exact():
    los = np.eye(3)
    result = build_double_difference_design(los, pivot_index=1, wavelength_m=0.25)
    assert result.pivot_index == 1
    assert result.satellite_indices == (0, 2)
    assert result.wavelength_m == 0.25
    assert np.array_equal(
        result.design_cycles_per_m,
        np.array([[4.0, -4.0, 0.0], [0.0, -4.0, 4.0]]),
    )
    with pytest.raises(CWLSError, match="unit vectors"):
        build_double_difference_design(2.0 * los, 0, 0.25)


def test_metric_adapter_reorders_full_covariance_scales_units_and_keeps_h_sign():
    code_m = np.array([2.0, -3.0])
    phase_m = np.array([0.2, -0.4])
    design = np.array([[-0.3, 0.1, 0.2], [0.4, -0.5, -0.1]])
    duplicated_design = np.vstack((design, design))
    factor = np.array(
        [
            [2.0, 0.0, 0.0, 0.0],
            [0.2, 1.7, 0.0, 0.0],
            [0.3, -0.1, 1.1, 0.0],
            [-0.2, 0.25, 0.15, 0.9],
        ]
    )
    covariance_code_phase = factor.dot(factor.T)
    wavelength = 0.2
    model = adapt_metric_double_differences(
        code_m=code_m,
        phase_m=phase_m,
        design_m_per_m=duplicated_design,
        covariance_code_phase_m2=covariance_code_phase,
        wavelength_m=wavelength,
        baseline_length_m=0.35,
    )
    permutation = np.array([2, 3, 0, 1])
    assert np.array_equal(model.phase_cycles, phase_m / wavelength)
    assert np.array_equal(model.code_cycles, code_m / wavelength)
    assert np.array_equal(model.design_cycles_per_m, design / wavelength)
    assert model.design_cycles_per_m[0, 0] < 0.0
    assert np.allclose(
        model.covariance_phase_code_cycles2,
        covariance_code_phase[np.ix_(permutation, permutation)] / wavelength**2,
    )
    assert model.covariance_phase_code_cycles2[0, -1] != 0.0


def test_full_nondiagonal_covariance_objective_matches_independent_oracle():
    model, direction, _ = _synthetic_model(6, seed=441, pivot_index=3)
    assert np.count_nonzero(model.covariance_phase_code_cycles2 - np.diag(
        np.diag(model.covariance_phase_code_cycles2)
    )) > 0
    probe = direction + np.array([0.03, -0.02, 0.01])
    assert wrapped_objective(model, probe) == pytest.approx(
        _oracle_wrapped_objective(model, probe), rel=2e-13, abs=2e-13
    )


def test_model_rejects_non_spd_or_wrong_order_sized_covariance():
    with pytest.raises(CWLSError, match="positive definite"):
        SingleBaselineCWLSModel(
            [0.0, 0.0],
            [0.0, 0.0],
            np.eye(2, 3),
            np.zeros((4, 4)),
            1.0,
        )
    with pytest.raises(CWLSError, match="expected shape"):
        SingleBaselineCWLSModel(
            [0.0, 0.0], [0.0, 0.0], np.eye(2, 3), np.eye(2), 1.0
        )


@pytest.mark.parametrize(
    ("phase", "row", "length", "expected"),
    [
        (1.25, [2.0, 0.0, 0.0], 0.5, (1, 2)),
        (2.0, [2.0, 0.0, 0.0], 0.5, (1, 3)),
        (-1.25, [0.0, 2.0, 0.0], 0.5, (-2, -1)),
        (0.5, [1.0, 0.0, 0.0], 0.5, (0, 1)),
    ],
)
def test_equation_58_integer_intervals_have_exact_inclusive_bounds(
    phase, row, length, expected
):
    interval = integer_ambiguity_interval(phase, row, length)
    assert (interval.lower, interval.upper) == expected
    assert tuple(interval.values()) == tuple(range(expected[0], expected[1] + 1))


def test_equation_58_empty_interval_has_stable_runner_code():
    with pytest.raises(CWLSGeometryError) as captured:
        integer_ambiguity_interval(0.5, [1.0, 0.0, 0.0], 0.1)
    assert captured.value.code == "NO_VALID_INTEGER_INTERVAL"


def test_search_circles_enumerate_every_integer_option_with_unit_normals():
    model = SingleBaselineCWLSModel(
        [0.25, -0.25],
        [0.0, 0.0],
        [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0]],
        np.eye(4),
        0.5,
    )
    circles = build_search_circles(model)
    assert len(circles) == 4
    assert [circle.ambiguity for circle in circles] == [0, 1, -1, 0]
    assert all(np.linalg.norm(circle.normal) == pytest.approx(1.0) for circle in circles)
    assert all(-1.0 <= circle.offset <= 1.0 for circle in circles)


def test_circle_geometry_two_intersections_is_full_sphere_and_satisfies_planes():
    first = SphereCircle([1.0, 0.0, 0.0], 0.0)
    second = SphereCircle([0.0, 1.0, 0.0], 0.0)
    result = intersect_sphere_circles(first, second)
    assert result.kind == "two_intersections"
    assert len(result.candidates) == 2
    assert np.allclose(result.candidates[0], [0.0, 0.0, -1.0])
    assert np.allclose(result.candidates[1], [0.0, 0.0, 1.0])
    for candidate in result.candidates:
        assert np.linalg.norm(candidate) == pytest.approx(1.0)
        assert first.normal.dot(candidate) == pytest.approx(first.offset)
        assert second.normal.dot(candidate) == pytest.approx(second.offset)


def test_circle_geometry_tangent_nonintersection_and_near_tangent_are_distinct():
    equator_x = SphereCircle([1.0, 0.0, 0.0], 0.0)
    tangent_point = SphereCircle([0.0, 1.0, 0.0], 1.0)
    tangent = intersect_sphere_circles(equator_x, tangent_point)
    assert tangent.kind == "point_intersection"
    assert len(tangent.candidates) == 1
    assert np.allclose(tangent.candidates[0], [0.0, 1.0, 0.0])

    outside = intersect_sphere_circles(
        SphereCircle([1.0, 0.0, 0.0], 0.9),
        SphereCircle([0.0, 1.0, 0.0], 0.9),
    )
    assert outside.kind == "separate"
    assert outside.candidates == ()

    near = intersect_sphere_circles(
        SphereCircle([1.0, 0.0, 0.0], 0.71),
        SphereCircle([0.0, 1.0, 0.0], 0.71),
    )
    assert DELTA_DELTA == 0.05
    assert near.kind == "near_tangent"
    assert len(near.candidates) == 1
    assert abs(near.delta_1) < DELTA_DELTA
    assert np.linalg.norm(near.candidates[0]) == pytest.approx(1.0)


def test_circle_geometry_explicit_parallel_antiparallel_and_point_degeneracies():
    base = SphereCircle([1.0, 0.0, 0.0], 0.2)
    parallel = intersect_sphere_circles(base, SphereCircle([1.0, 0.0, 0.0], 0.2))
    assert parallel.kind == "coincident_parallel"
    assert parallel.parallel_relation == "parallel"
    assert parallel.candidates == ()
    disjoint = intersect_sphere_circles(base, SphereCircle([1.0, 0.0, 0.0], -0.2))
    assert disjoint.kind == "disjoint_parallel"

    antiparallel = intersect_sphere_circles(
        base, SphereCircle([-1.0, 0.0, 0.0], -0.2)
    )
    assert antiparallel.kind == "coincident_antiparallel"
    assert antiparallel.parallel_relation == "antiparallel"
    anti_disjoint = intersect_sphere_circles(
        base, SphereCircle([-1.0, 0.0, 0.0], 0.2)
    )
    assert anti_disjoint.kind == "disjoint_antiparallel"

    point_hit = intersect_sphere_circles(
        SphereCircle([0.0, 0.0, 1.0], 1.0),
        SphereCircle([1.0, 0.0, 0.0], 0.0),
    )
    assert point_hit.kind == "point_intersection"
    assert np.allclose(point_hit.candidates[0], [0.0, 0.0, 1.0])


def test_machine_precision_dedup_is_deterministic_but_keeps_scientific_neighbors():
    eps = np.finfo(float).eps
    directions = deduplicate_directions_machine_precision(
        [
            [1.0, 0.0, 0.0],
            [1.0, 2.0 * eps, 0.0],
            [1.0, 1.0e-10, 0.0],
            [-1.0, 0.0, 0.0],
        ]
    )
    assert len(directions) == 3
    assert np.allclose(directions[0], [-1.0, 0.0, 0.0])
    assert all(np.linalg.norm(direction) == pytest.approx(1.0) for direction in directions)


def test_candidate_pool_has_no_k_cap_and_serializes_required_algorithm1_counts():
    model, _, _ = _synthetic_model(7, seed=777, pivot_index=5)
    pool = generate_candidate_pool(model)
    assert pool.phase_row_count == 6
    assert len(pool.integer_option_count_per_row) == 6
    assert sum(pool.integer_option_count_per_row) == len(pool.circles)
    assert pool.pair_count == len(pool.pair_geometries)
    assert pool.raw_candidate_count >= len(pool.directions)
    assert len(pool.directions) > 10  # deliberately larger than a typical best-K shortlist
    assert pool.intersecting_pair_count == sum(
        item.kind in {"two_intersections", "tangent", "point_intersection"}
        for item in pool.pair_geometries
    )
    assert pool.near_tangent_candidate_count == sum(
        len(item.candidates)
        for item in pool.pair_geometries
        if item.kind in {"near_tangent", "point_near_tangent"}
    )
    assert pool.degenerate_pair_count == sum(
        item.parallel_relation is not None or item.kind.startswith("point_")
        for item in pool.pair_geometries
    )
    assert all(np.linalg.norm(direction) == pytest.approx(1.0) for direction in pool.directions)


def test_sphere_quadratic_linear_case_has_analytic_global_solution():
    linear = np.array([1.0, -2.0, 3.0])
    solution = solve_unit_sphere_quadratic(np.zeros((3, 3)), linear)
    assert np.allclose(solution.direction, linear / np.linalg.norm(linear), atol=2e-15)
    assert solution.objective == pytest.approx(-2.0 * np.linalg.norm(linear))
    assert solution.global_certified
    assert not solution.hard_case
    assert solution.psd_margin >= 0.0
    assert solution.duality_gap < 1e-12


def test_sphere_quadratic_hard_case_is_deterministic_and_globally_certified():
    matrix = np.diag([0.0, 0.0, 2.0])
    linear = np.array([0.0, 0.0, 0.5])
    first = solve_unit_sphere_quadratic(matrix, linear)
    second = solve_unit_sphere_quadratic(matrix, linear)
    assert first.hard_case
    assert first.global_certified
    assert np.array_equal(first.direction, second.direction)
    assert first.direction[0] > 0.0
    assert first.direction[1] == 0.0
    assert first.direction[2] == pytest.approx(0.25)
    assert np.linalg.norm(first.direction) == pytest.approx(1.0)
    assert first.stationarity_residual < 1e-12
    assert first.duality_gap < 1e-12


def test_sphere_quadratic_beats_independent_dense_random_global_oracle():
    matrix = np.array(
        [[-2.0, 0.3, -0.1], [0.3, 1.0, 0.25], [-0.1, 0.25, 3.0]]
    )
    linear = np.array([0.7, -0.2, 0.4])
    solution = solve_unit_sphere_quadratic(matrix, linear)
    rng = np.random.default_rng(919)
    probes = rng.normal(size=(100_000, 3))
    probes /= np.linalg.norm(probes, axis=1)[:, None]
    values = np.einsum("ni,ij,nj->n", probes, matrix, probes) - 2.0 * probes.dot(linear)
    assert solution.objective <= float(values.min()) + 1e-12
    assert solution.global_certified
    assert solution.stationarity_residual < 1e-9
    assert solution.unit_norm_residual < 1e-12
    assert solution.duality_gap < 1e-9


@pytest.mark.parametrize("satellite_count", range(4, 9))
def test_faithful_low_noise_recovery_for_4_to_8_satellites_random_full_sphere_and_pivots(
    satellite_count,
):
    pivot_index = satellite_count - 4
    model, true_direction, true_ambiguities = _synthetic_model(
        satellite_count,
        seed=1200 + satellite_count,
        pivot_index=pivot_index,
    )
    solution = solve_single_baseline_cwls(model)
    angle_error = math.acos(float(np.clip(solution.direction.dot(true_direction), -1.0, 1.0)))
    assert angle_error < 0.002
    assert solution.integer_ambiguities == tuple(int(value) for value in true_ambiguities)
    assert np.linalg.norm(solution.direction) == pytest.approx(1.0)
    assert np.allclose(solution.baseline_vector_m, 0.35 * solution.direction)
    assert solution.objective == pytest.approx(
        _oracle_wrapped_objective(model, solution.direction), rel=2e-12, abs=2e-12
    )
    assert solution.candidate_count == len(solution.diagnostics)
    assert solution.candidate_count > 0
    assert all(
        item.converged and item.failure_code is None
        for item in solution.diagnostics
    )
    assert solution.phase_row_count == satellite_count - 1
    assert sum(solution.integer_option_count_per_row) == solution.circle_count
    selected = solution.diagnostics[solution.selected_candidate_index]
    assert selected.converged
    assert selected.convergence_state == "CONVERGED_INTEGER_STABLE_DIRECTION"
    assert selected.integer_vector_stable
    assert selected.iteration_count == len(selected.iterations)
    assert selected.iteration_count <= REFINEMENT_MAX_ITERATIONS
    assert selected.unit_norm_error < 1e-12
    assert selected.refined_unwrapped_objective >= 0.0
    assert all(item.sphere_solution.global_certified for item in selected.iterations)


def test_noise_free_compatible_model_recovers_direction_and_integer_vector_numerically():
    model, true_direction, true_ambiguities = _synthetic_model(
        7, seed=1601, pivot_index=4, add_low_noise=False
    )
    solution = solve_single_baseline_cwls(model)
    assert np.allclose(solution.direction, true_direction, rtol=0.0, atol=5e-14)
    assert solution.integer_ambiguities == tuple(int(value) for value in true_ambiguities)
    assert solution.objective < 1e-20
    assert solution.diagnostics[solution.selected_candidate_index].integer_vector_stable


@pytest.mark.parametrize(
    ("satellite_count", "seed", "pivot_index"),
    [(4, 1701, 0), (5, 1702, 2), (6, 1703, 5)],
)
def test_complete_cwls_solution_is_not_beaten_by_independent_dense_full_sphere_oracle(
    satellite_count, seed, pivot_index
):
    narrow_model, _, _ = _synthetic_model(
        satellite_count, seed=seed, pivot_index=pivot_index
    )
    # A broader, still full/non-diagonal covariance makes the fixed dense grid a
    # meaningful whole-objective screen rather than a test of sub-grid sharpness.
    covariance = _full_covariance(0.05, 0.10, satellite_count - 1)
    model = SingleBaselineCWLSModel(
        narrow_model.phase_cycles,
        narrow_model.code_cycles,
        narrow_model.design_cycles_per_m,
        covariance,
        narrow_model.baseline_length_m,
    )
    solution = solve_single_baseline_cwls(model)
    oracle_at_solution = _oracle_wrapped_objective(model, solution.direction)
    dense_minimum = _dense_fibonacci_wrapped_objective_minimum(model)
    assert solution.objective == pytest.approx(oracle_at_solution, rel=2e-12, abs=2e-12)
    assert solution.objective <= dense_minimum + DENSE_ORACLE_MATERIAL_TOL


def test_boundary_tie_is_deterministic_and_uses_exact_original_objective():
    model = SingleBaselineCWLSModel(
        phase_cycles=np.zeros(2),
        code_cycles=np.zeros(2),
        design_cycles_per_m=np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        covariance_phase_code_cycles2=np.eye(4),
        baseline_length_m=1.0,
    )
    first = solve_single_baseline_cwls(model)
    second = solve_single_baseline_cwls(model)
    assert np.array_equal(first.direction, second.direction)
    assert np.array_equal(first.direction, [0.0, 0.0, 1.0])
    assert first.objective == 0.0
    assert first.exact_objective_tie_count == 2
    assert first.integer_ambiguities == (0, 0)
    assert first.candidate_count == len(first.diagnostics)
    assert all(diagnostic.converged for diagnostic in first.diagnostics)


def test_fractional_phase_bias_is_reported_as_residual_stress_not_calibrated_away():
    unbiased, true_direction, _ = _synthetic_model(
        7, seed=882, pivot_index=2, add_low_noise=False
    )
    biased = SingleBaselineCWLSModel(
        phase_cycles=unbiased.phase_cycles + 0.20,
        code_cycles=unbiased.code_cycles,
        design_cycles_per_m=unbiased.design_cycles_per_m,
        covariance_phase_code_cycles2=_full_covariance(0.01, 0.08, 6),
        baseline_length_m=unbiased.baseline_length_m,
    )
    unbiased_comparable = SingleBaselineCWLSModel(
        phase_cycles=unbiased.phase_cycles,
        code_cycles=unbiased.code_cycles,
        design_cycles_per_m=unbiased.design_cycles_per_m,
        covariance_phase_code_cycles2=biased.covariance_phase_code_cycles2,
        baseline_length_m=unbiased.baseline_length_m,
    )
    clean_solution = solve_single_baseline_cwls(unbiased_comparable)
    biased_solution = solve_single_baseline_cwls(biased)
    clean_diagnostic = clean_solution.diagnostics[clean_solution.selected_candidate_index]
    biased_diagnostic = biased_solution.diagnostics[biased_solution.selected_candidate_index]
    assert clean_solution.direction.dot(true_direction) == pytest.approx(1.0, abs=1e-13)
    assert biased_diagnostic.wrapped_phase_rms_cycles > 0.05
    assert biased_diagnostic.wrapped_phase_max_abs_cycles > 0.10
    assert biased_solution.objective > clean_solution.objective + 100.0
    assert biased_diagnostic.wrapped_phase_residual_cycles != (0.0,) * 6


def test_solution_refines_every_unique_candidate_without_truncation():
    model, _, _ = _synthetic_model(6, seed=313, pivot_index=4)
    pool = generate_candidate_pool(model)
    solution = solve_single_baseline_cwls(model)
    assert solution.candidate_count == len(pool.directions)
    assert len(solution.diagnostics) == len(pool.directions)
    assert [item.coarse_index for item in solution.diagnostics] == list(
        range(len(pool.directions))
    )
    assert REFINEMENT_TOL == 1e-10
    assert REFINEMENT_MAX_ITERATIONS == 20
    assert all(
        item.converged and item.failure_code is None
        for item in solution.diagnostics
    )


def test_final_selection_excludes_nonconverged_candidates_and_raises_if_all_fail(monkeypatch):
    model = SingleBaselineCWLSModel(
        np.zeros(2), np.zeros(2), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], np.eye(4), 1.0
    )
    original = ext02._refine_candidate

    def force_failure(model_arg, coarse_index, coarse_direction, cache):
        diagnostic = original(model_arg, coarse_index, coarse_direction, cache)
        return replace(
            diagnostic,
            converged=False,
            convergence_state="MAX_ITERATIONS_DIRECTION_NOT_CONVERGED",
        )

    monkeypatch.setattr(ext02, "_refine_candidate", force_failure)
    with pytest.raises(CWLSNumericalError, match="ALL_REFINEMENTS_FAILED") as captured:
        solve_single_baseline_cwls(model)
    assert captured.value.code == "ALL_REFINEMENTS_FAILED"
    assert len(captured.value.candidate_diagnostics) == len(
        generate_candidate_pool(model).directions
    )
    assert captured.value.candidate_pool is not None


def test_one_candidate_sphere_failure_attempts_all_others_then_rejects_incomplete_pool(
    monkeypatch,
):
    model = SingleBaselineCWLSModel(
        np.zeros(2), np.zeros(2), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], np.eye(4), 1.0
    )
    pool = generate_candidate_pool(model)
    original = ext02._refine_candidate
    attempted: list[int] = []

    def fail_once(model_arg, coarse_index, coarse_direction, cache):
        attempted.append(coarse_index)
        if coarse_index == 0:
            raise CWLSNumericalError(
                "injected candidate-local sphere failure", code="SPHERE_SOLVER_FAILURE"
            )
        return original(model_arg, coarse_index, coarse_direction, cache)

    monkeypatch.setattr(ext02, "_refine_candidate", fail_once)
    with pytest.raises(
        CWLSNumericalError, match="INCOMPLETE_CANDIDATE_REFINEMENT_POOL"
    ) as captured:
        solve_single_baseline_cwls(model)
    assert captured.value.code == "SPHERE_SOLVER_FAILURE"
    assert attempted == list(range(len(pool.directions)))
    diagnostics = captured.value.candidate_diagnostics
    assert len(diagnostics) == len(pool.directions)
    assert len(captured.value.candidate_pool.directions) == len(pool.directions)
    assert captured.value.candidate_pool.raw_candidate_count == pool.raw_candidate_count
    failed = [item for item in diagnostics if item.failure_code is not None]
    assert len(failed) == 1
    assert failed[0].failure_code == "SPHERE_SOLVER_FAILURE"
    assert failed[0].convergence_state == "FAILED_SPHERE_SOLVER_FAILURE"
    assert not failed[0].converged
    assert failed[0].objective is None
    assert failed[0].refined_unwrapped_objective is None
    assert all(item.converged for item in diagnostics[1:])


def test_one_nonconverged_candidate_attempts_complete_pool_then_raises_numerical_failure(
    monkeypatch,
):
    model = SingleBaselineCWLSModel(
        np.zeros(2), np.zeros(2), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], np.eye(4), 1.0
    )
    pool = generate_candidate_pool(model)
    original = ext02._refine_candidate
    attempted: list[int] = []

    def mark_first_nonconverged(model_arg, coarse_index, coarse_direction, cache):
        attempted.append(coarse_index)
        diagnostic = original(model_arg, coarse_index, coarse_direction, cache)
        if coarse_index == 0:
            return replace(
                diagnostic,
                converged=False,
                convergence_state="MAX_ITERATIONS_DIRECTION_NOT_CONVERGED",
            )
        return diagnostic

    monkeypatch.setattr(ext02, "_refine_candidate", mark_first_nonconverged)
    with pytest.raises(
        CWLSNumericalError, match="INCOMPLETE_CANDIDATE_REFINEMENT_POOL"
    ) as captured:
        solve_single_baseline_cwls(model)
    assert captured.value.code == "NUMERICAL_FAILURE"
    assert attempted == list(range(len(pool.directions)))
    assert len(captured.value.candidate_diagnostics) == len(pool.directions)
    assert len(captured.value.candidate_pool.directions) == len(pool.directions)


def test_final_exact_tie_orders_integer_ambiguity_before_coarse_provenance(monkeypatch):
    model = SingleBaselineCWLSModel(
        np.zeros(2), np.zeros(2), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], np.eye(4), 1.0
    )
    original = ext02._refine_candidate

    def make_tied(model_arg, coarse_index, coarse_direction, cache):
        diagnostic = original(model_arg, coarse_index, coarse_direction, cache)
        ambiguity = (0, 1) if coarse_index == 1 else (1 + coarse_index, 0)
        return replace(
            diagnostic,
            refined_direction=np.array([0.0, 0.0, 1.0]),
            objective=0.0,
            integer_ambiguities=ambiguity,
            integer_corrections=tuple(-value for value in ambiguity),
            converged=True,
            integer_vector_stable=True,
            convergence_state="CONVERGED_INTEGER_STABLE_DIRECTION",
        )

    monkeypatch.setattr(ext02, "_refine_candidate", make_tied)
    solution = solve_single_baseline_cwls(model)
    assert solution.selected_candidate_index == 1
    assert solution.integer_ambiguities == (0, 1)


def test_parallel_only_geometry_fails_closed_without_fabricated_candidate():
    model = SingleBaselineCWLSModel(
        [0.0, 0.0],
        [0.0, 0.0],
        [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        np.eye(4),
        0.2,
    )
    with pytest.raises(CWLSGeometryError, match="no finite direction candidates") as captured:
        generate_candidate_pool(model)
    assert captured.value.code == "NO_CIRCLE_PAIR_CANDIDATE"
