import os

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import (
    FloatSolution,
    RTKLIBLambdaBridge,
    SearchIncomplete,
    SearchTimeout,
    body_yaw_from_ned_baseline,
    constrained_baseline,
    evaluate_candidate,
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
    timed_out = search_strict_lambda(
        crafted, bridge, initial_candidate_count=2,
        node_limit=10_000, timeout_seconds=0.0,
    )
    assert not timed_out[4] and timed_out[5] == SearchTimeout.code

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


def test_ned_physical_transform_wraps_crossing_boundary():
    # Baseline beta just above +90 degrees gives body yaw just below -180.
    yaw = body_yaw_from_ned_baseline([-1e-6, 0.350, 0.0])
    assert -180.0 <= yaw < -179.9
    assert wrap_safe_residual_degrees(-179.9, 179.9) == pytest.approx(0.2)
