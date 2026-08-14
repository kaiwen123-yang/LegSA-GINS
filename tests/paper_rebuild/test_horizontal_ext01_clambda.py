import os

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import (
    FloatSolution,
    GLOBAL_BOUND_CERTIFIED,
    NUMERICAL_FAILURE,
    RTKLIBLambdaBridge,
    SearchIncomplete,
    SearchTimeout,
    body_yaw_from_ned_baseline,
    constrained_baseline,
    evaluate_candidate,
    evaluate_production_objective,
    joint_gls,
    search_exact,
    search_strict_lambda,
    solve_clambda,
    wrap_safe_residual_degrees,
)


@pytest.fixture(scope="module")
def rtklib_lambda_bridge_path():
    path = os.environ.get("LEGSA_RTKLIB_LAMBDA_BRIDGE")
    if not path:
        pytest.skip("LEGSA_RTKLIB_LAMBDA_BRIDGE is not configured")
    return path


def _problem(noise=0.0):
    rng = np.random.default_rng(11)
    ambiguity = np.array([2, -1])
    baseline = np.array([0.21, 0.28, 0.0])  # exactly 0.350 m
    design = rng.normal(size=(12, 5))
    a, b = design[:, :2], design[:, 2:]
    y = a @ ambiguity + b @ baseline
    y = y + noise * rng.normal(size=y.size)
    return y, a, b, np.eye(y.size) * 0.01, ambiguity, baseline


def _crafted_far_constraint_solution():
    """A C-LAMBDA optimum absent from the first two ordinary-LAMBDA seeds."""
    qaa = np.array([[1.0]])
    qba = np.array([[0.1], [0.0], [0.0]])
    conditional = np.eye(3) * 0.0001
    covariance_joint = np.block([
        [qaa, qba.T],
        [qba, conditional + qba @ qba.T],
    ])
    return FloatSolution(
        ambiguity=np.array([0.1]), baseline=np.array([0.02, 0.0, 0.0]),
        covariance=covariance_joint, covariance_aa=qaa, covariance_ba=qba,
        conditional_covariance_b=conditional, residual_objective=0.0,
    )


@pytest.mark.parametrize("noise", [0.0, 1e-4])
def test_known_short_baseline_noiseless_and_low_noise(noise):
    y, a, b, covariance, ambiguity, baseline = _problem(noise)
    result = solve_clambda(y, a, b, covariance)
    np.testing.assert_array_equal(result.best.ambiguity, ambiguity)
    assert np.linalg.norm(result.best.baseline) == pytest.approx(0.350, abs=1e-9)
    np.testing.assert_allclose(result.best.baseline, baseline, atol=5e-4)
    assert result.search_complete


def test_sphere_solver_inside_outside_on_sphere_and_degeneracy():
    covariance = np.diag([1.0, 2.0, 3.0])
    for center in ([0.1, 0.0, 0.0], [0.8, 0.0, 0.0], [0.35, 0.0, 0.0]):
        result = constrained_baseline(center, covariance, 0.350)
        assert np.linalg.norm(result.baseline) == pytest.approx(0.350, abs=1e-9)
    hard = constrained_baseline([0.0, 0.0, 0.0], np.eye(3), 0.350)
    assert hard.hard_case and np.linalg.norm(hard.baseline) == pytest.approx(0.350)

    anisotropic = np.diag([0.25, 1.0, 4.0])
    weight = np.linalg.inv(anisotropic)
    for signed_tiny in (1e-12, -1e-12):
        center = np.array([0.0, 0.0, signed_tiny])
        solved = constrained_baseline(center, anisotropic, 0.350)
        assert not solved.hard_case
        assert np.sign(solved.baseline[2]) == np.sign(signed_tiny)
        assert solved.constraint_error_m < 1e-9
        opposite = solved.baseline.copy()
        opposite[2] *= -1
        selected_objective = (solved.baseline - center) @ weight @ (solved.baseline - center)
        opposite_objective = (opposite - center) @ weight @ (opposite - center)
        assert selected_objective < opposite_objective


def test_full_constrained_objective_changes_candidate_ranking_and_search_exhaustion_fails_closed():
    y, a, b, covariance, _, _ = _problem(0.0)
    floating = joint_gls(y, a, b, covariance)
    true = evaluate_candidate(floating, [2, -1], 0.350)
    other = evaluate_candidate(floating, [3, -1], 0.350)
    assert true.objective < other.objective
    assert other.objective == pytest.approx(other.ambiguity_objective + other.baseline_objective)
    with pytest.raises(ValueError, match="integer valued"):
        evaluate_candidate(floating, [2.25, -1], 0.350)

    # Ordinary LAMBDA chooses 0 because 0.1 is nearer to 0 than 1.  The exact
    # joint constrained objective chooses 1 because its conditional baseline is
    # physically close to the 0.350 m sphere.  This cannot be reproduced by
    # normalizing or post-gating the ordinary winner.
    qaa = np.array([[1.0]])
    qba = np.array([[0.3], [0.0], [0.0]])
    conditional = np.eye(3) * 0.001
    covariance_joint = np.block([
        [qaa, qba.T],
        [qba, conditional + qba @ qba.T],
    ])
    crafted = FloatSolution(
        ambiguity=np.array([0.1]), baseline=np.array([0.02, 0.0, 0.0]),
        covariance=covariance_joint, covariance_aa=qaa, covariance_ba=qba,
        conditional_covariance_b=conditional, residual_objective=0.0,
    )
    ordinary_winner = 0
    exact_zero = evaluate_candidate(crafted, [0], 0.350)
    exact_one = evaluate_candidate(crafted, [1], 0.350)
    assert ordinary_winner == 0
    assert exact_one.objective < exact_zero.objective
    with pytest.raises(SearchIncomplete, match=SearchIncomplete.code):
        solve_clambda(y, a, b, covariance, node_limit=1)


def test_production_objective_decomposition_sums_and_matches_whitened_residual():
    y, a, b, covariance, ambiguity, _ = _problem(1e-4)
    floating = joint_gls(y, a, b, covariance)
    audited = evaluate_production_objective(
        floating, ambiguity, 0.350, y, a, b, covariance,
        code_observation_count=y.size // 2,
    )
    candidate = audited.candidate
    assert candidate.total_constrained_objective == pytest.approx(
        candidate.ambiguity_quadratic_term
        + candidate.conditional_baseline_constraint_term,
        abs=1e-12,
    )
    assert audited.whitened_total_residual_squared == pytest.approx(
        audited.float_residual_objective + audited.total_constrained_objective,
        rel=1e-9, abs=1e-9,
    )
    assert audited.objective_identity_error == pytest.approx(0.0, abs=1e-9)
    assert audited.code_phase_cross_covariance_zero
    assert audited.whitened_total_residual_norm ** 2 == pytest.approx(
        audited.whitened_code_residual_norm ** 2
        + audited.whitened_phase_residual_norm ** 2,
        abs=1e-9,
    )


def test_proxy_candidate_objective_evaluation():
    """A diagnostic candidate is evaluated without a second objective path."""
    y, a, b, covariance, true_ambiguity, _ = _problem(2e-4)
    floating = joint_gls(y, a, b, covariance)
    production_best, _, _, _ = search_exact(floating, node_limit=100_000)
    proxy_integer = np.rint(true_ambiguity.astype(float)).astype(int)
    proxy_audit = evaluate_production_objective(
        floating, proxy_integer, 0.350, y, a, b, covariance,
        code_observation_count=y.size // 2,
    )
    direct = evaluate_candidate(floating, proxy_integer, 0.350)
    assert proxy_audit.candidate.objective == pytest.approx(direct.objective, abs=1e-12)
    assert proxy_audit.candidate.ambiguity_objective == pytest.approx(
        direct.ambiguity_objective, abs=1e-12
    )
    assert proxy_audit.candidate.baseline_objective == pytest.approx(
        direct.baseline_objective, abs=1e-12
    )
    assert proxy_audit.total_constrained_objective >= production_best.objective - 1e-10


def test_rtklib_column_major_wrapper_matches_official_utest1(rtklib_lambda_bridge_path):
    # RTKLIB test/utest/t_lambda.c utest1 (Takasu RTKLIB).  This checks both
    # the standard implementation and the n-by-m Fortran output convention.
    ambiguity = np.array([
        1585184.171, -6716599.430, 3915742.905,
        7627233.455, 9565990.879, 989457273.200,
    ])
    covariance = np.array([
        [0.227134, 0.112202, 0.112202, 0.112202, 0.112202, 0.103473],
        [0.112202, 0.227134, 0.112202, 0.112202, 0.112202, 0.103473],
        [0.112202, 0.112202, 0.227134, 0.112202, 0.112202, 0.103473],
        [0.112202, 0.112202, 0.112202, 0.227134, 0.112202, 0.103473],
        [0.112202, 0.112202, 0.112202, 0.112202, 0.227134, 0.103473],
        [0.103473, 0.103473, 0.103473, 0.103473, 0.103473, 0.434339],
    ])
    expected = np.array([
        [1585184, 1585184],
        [-6716599, -6716600],
        [3915743, 3915743],
        [7627234, 7627233],
        [9565991, 9565991],
        [989457273, 989457273],
    ])
    candidates = RTKLIBLambdaBridge(rtklib_lambda_bridge_path).candidates(
        ambiguity, covariance, 2
    )
    np.testing.assert_array_equal(
        np.column_stack([candidate.ambiguity for candidate in candidates]), expected
    )
    np.testing.assert_allclose(
        [candidate.ambiguity_objective for candidate in candidates],
        [3.507984, 3.708456], atol=1e-5,
    )


def test_reduced_best_first_search_matches_finite_oracle(rtklib_lambda_bridge_path):
    y, a, b, covariance, _, _ = _problem(1e-4)
    floating = joint_gls(y, a, b, covariance)
    finite_best, finite_second, _, _ = search_exact(floating, node_limit=100_000)
    strict = search_strict_lambda(
        floating, RTKLIBLambdaBridge(rtklib_lambda_bridge_path),
        initial_candidate_count=2, node_limit=100_000, timeout_seconds=5.0,
    )
    best, second, _, _, complete, failure, frontier_bound = strict
    assert complete and failure is None
    np.testing.assert_array_equal(best.ambiguity, finite_best.ambiguity)
    np.testing.assert_array_equal(second.ambiguity, finite_second.ambiguity)
    assert best.objective == pytest.approx(finite_best.objective, abs=1e-9)
    assert second.objective == pytest.approx(finite_second.objective, abs=1e-9)
    assert frontier_bound >= second.objective - 1e-10


def test_search_matches_bruteforce(
        rtklib_lambda_bridge_path):
    rng = np.random.default_rng(20260815)
    bridge = RTKLIBLambdaBridge(rtklib_lambda_bridge_path)
    for dimension in (1, 2, 3):
        for _ in range(12):
            ambiguity = rng.uniform(-1.5, 1.5, size=dimension)
            q_factor = rng.normal(scale=0.12, size=(dimension, dimension))
            qaa = q_factor @ q_factor.T + np.eye(dimension) * 0.04
            qba = rng.normal(scale=0.025, size=(3, dimension))
            conditional = np.diag(rng.uniform(0.002, 0.015, size=3))
            qbb = conditional + qba @ np.linalg.solve(qaa, qba.T)
            covariance_joint = np.block([[qaa, qba.T], [qba, qbb]])
            baseline = rng.normal(size=3)
            baseline *= rng.uniform(0.20, 0.50) / np.linalg.norm(baseline)
            floating = FloatSolution(
                ambiguity=ambiguity,
                baseline=baseline,
                covariance=covariance_joint,
                covariance_aa=qaa,
                covariance_ba=qba,
                conditional_covariance_b=conditional,
                residual_objective=0.0,
            )
            finite_best, finite_second, _, _ = search_exact(
                floating, node_limit=2_000_000
            )
            strict = search_strict_lambda(
                floating, bridge, initial_candidate_count=2,
                node_limit=None, timeout_seconds=5.0,
            )
            assert strict.certificate.global_optimum_certified
            assert strict.certificate.termination_reason == GLOBAL_BOUND_CERTIFIED
            np.testing.assert_array_equal(strict.best.ambiguity, finite_best.ambiguity)
            np.testing.assert_array_equal(strict.second.ambiguity, finite_second.ambiguity)
            assert strict.best.objective == pytest.approx(finite_best.objective, abs=2e-8)
            assert strict.second.objective == pytest.approx(finite_second.objective, abs=2e-8)
            assert strict.certificate.frontier_lower_bound_at_termination >= (
                strict.second.objective - 2e-8
            )


def test_search_certificate_no_hidden_cap(
        rtklib_lambda_bridge_path):
    floating = _crafted_far_constraint_solution()
    bridge = RTKLIBLambdaBridge(rtklib_lambda_bridge_path)
    seeds = bridge.candidates(floating.ambiguity, floating.covariance_aa, 2)
    assert [tuple(item.ambiguity) for item in seeds] == [(0,), (1,)]

    strict = search_strict_lambda(
        floating, bridge, initial_candidate_count=2,
        node_limit=None, timeout_seconds=5.0,
    )
    certificate = strict.certificate
    assert tuple(strict.best.ambiguity) == (3,)
    assert tuple(strict.best.ambiguity) not in {tuple(item.ambiguity) for item in seeds}
    assert certificate.lambda_seed_count_requested == 2
    assert certificate.lambda_seed_count_returned == 2
    assert certificate.unique_integer_candidates_evaluated > 2
    assert certificate.integer_leaves_evaluated > 0
    assert certificate.branch_and_bound_nodes_expanded >= certificate.integer_leaves_evaluated
    assert certificate.candidate_cap_applied is False
    assert certificate.configured_node_limit is None
    assert certificate.node_limit_exhausted is False
    assert certificate.global_optimum_certified
    assert certificate.termination_reason == GLOBAL_BOUND_CERTIFIED
    assert certificate.best_total_objective == pytest.approx(strict.best.objective)
    assert certificate.second_total_objective == pytest.approx(strict.second.objective)
    assert certificate.frontier_lower_bound_at_termination >= (
        certificate.second_total_objective - 1e-10
    )

    # Exhaustive local enumeration around the deliberately nonlocal proxy
    # candidate independently confirms the certificate on this 1-D case.
    exhaustive = sorted(
        (evaluate_candidate(floating, [integer], 0.350)
         for integer in range(-30, 31)),
        key=lambda candidate: (candidate.objective, tuple(candidate.ambiguity)),
    )
    np.testing.assert_array_equal(strict.best.ambiguity, exhaustive[0].ambiguity)
    np.testing.assert_array_equal(strict.second.ambiguity, exhaustive[1].ambiguity)


def test_reported_node_limit_never_yields_a_false_global_certificate(
        rtklib_lambda_bridge_path):
    strict = search_strict_lambda(
        _crafted_far_constraint_solution(),
        RTKLIBLambdaBridge(rtklib_lambda_bridge_path),
        initial_candidate_count=2, node_limit=1, timeout_seconds=5.0,
    )
    certificate = strict.certificate
    assert strict.failure_code == SearchIncomplete.code
    assert certificate.termination_reason == NUMERICAL_FAILURE
    assert not certificate.global_optimum_certified
    assert certificate.configured_node_limit == 1
    assert certificate.node_limit_exhausted
    assert not certificate.runtime_budget_exhausted
    assert not certificate.candidate_cap_applied


def test_strict_search_finds_constraint_selected_candidate_and_fails_per_epoch(
        rtklib_lambda_bridge_path):
    qaa = np.array([[1.0]])
    qba = np.array([[0.3], [0.0], [0.0]])
    conditional = np.eye(3) * 0.001
    covariance_joint = np.block([
        [qaa, qba.T],
        [qba, conditional + qba @ qba.T],
    ])
    crafted = FloatSolution(
        ambiguity=np.array([0.1]), baseline=np.array([0.02, 0.0, 0.0]),
        covariance=covariance_joint, covariance_aa=qaa, covariance_ba=qba,
        conditional_covariance_b=conditional, residual_objective=0.0,
    )
    brute = sorted(
        (evaluate_candidate(crafted, [integer], 0.350) for integer in range(-20, 21)),
        key=lambda candidate: (candidate.objective, tuple(candidate.ambiguity)),
    )
    bridge = RTKLIBLambdaBridge(rtklib_lambda_bridge_path)
    best, second, _, _, complete, failure, bound = search_strict_lambda(
        crafted, bridge, initial_candidate_count=2,
        node_limit=10_000, timeout_seconds=5.0,
    )
    assert complete and failure is None
    np.testing.assert_array_equal(best.ambiguity, brute[0].ambiguity)
    np.testing.assert_array_equal(second.ambiguity, brute[1].ambiguity)
    assert bound >= second.objective - 1e-10

    incomplete = search_strict_lambda(
        crafted, bridge, initial_candidate_count=2,
        node_limit=1, timeout_seconds=5.0,
    )
    assert not incomplete[4] and incomplete[5] == SearchIncomplete.code
    assert incomplete.certificate.termination_reason == NUMERICAL_FAILURE
    assert incomplete.certificate.node_limit_exhausted
    assert not incomplete.certificate.global_optimum_certified
    timed_out = search_strict_lambda(
        crafted, bridge, initial_candidate_count=2,
        node_limit=10_000, timeout_seconds=0.0,
    )
    assert not timed_out[4] and timed_out[5] == SearchTimeout.code
    assert timed_out.certificate.termination_reason == SearchTimeout.code
    assert timed_out.certificate.runtime_budget_exhausted

    y, a, b, observation_covariance, _, _ = _problem()
    epoch_result = solve_clambda(
        y, a, b, observation_covariance,
        lambda_bridge_path=rtklib_lambda_bridge_path,
        strict=True, timeout_seconds=0.0,
    )
    assert epoch_result.status == "invalid"
    assert epoch_result.failure_code == SearchTimeout.code
    assert not epoch_result.search_complete
    assert epoch_result.best is None
    assert not epoch_result.integer_solution_returned
    assert not epoch_result.global_optimum_certified
    assert epoch_result.runtime_budget_exhausted
    assert epoch_result.ambiguity_acceptance_test_defined is False
    assert epoch_result.ambiguity_accepted is None


def test_solution_labels_separate_integer_return_search_certificate_and_acceptance(
        rtklib_lambda_bridge_path):
    y, a, b, observation_covariance, _, _ = _problem(1e-4)
    result = solve_clambda(
        y, a, b, observation_covariance,
        lambda_bridge_path=rtklib_lambda_bridge_path,
        strict=True, initial_candidate_count=2,
        strict_node_limit=None, timeout_seconds=5.0,
    )
    assert result.integer_solution_returned
    assert result.search_complete
    assert result.global_optimum_certified
    assert result.termination_reason == GLOBAL_BOUND_CERTIFIED
    assert not result.runtime_budget_exhausted
    assert result.ambiguity_acceptance_test_defined is False
    assert result.ambiguity_accepted is None
    assert result.lambda_seed_count_requested == 2
    assert result.lambda_seed_count_returned == 2
    assert result.nodes_visited == result.branch_and_bound_nodes_expanded
    assert result.candidates_evaluated == result.unique_integer_candidates_evaluated
    assert result.frontier_lower_bound_at_termination == result.completion_bound
    assert result.best_total_objective == pytest.approx(result.best.objective)
    assert result.second_total_objective == pytest.approx(result.second.objective)


def test_ned_physical_transform_wraps_crossing_boundary():
    # Baseline beta just above +90 degrees gives body yaw just below -180.
    yaw = body_yaw_from_ned_baseline([-1e-6, 0.350, 0.0])
    assert -180.0 <= yaw < -179.9
    assert wrap_safe_residual_degrees(-179.9, 179.9) == pytest.approx(0.2)
