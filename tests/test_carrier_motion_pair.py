"""Independent analytic checks for the two-epoch motion bound.

These tests do not search integers, load LAMBDA, read recorded data, or use a
reference trajectory.  Feasible points are constructed analytically rather
than copied from the implementation's secular-root or bound formula.
"""
import math

import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.motion_pair import (
    PairEvaluator,
    PairMotionConstraint,
    angle_motion_increment,
    feasible_pair,
)
from legsa_gins.paper_rebuild.carrier_phase.temporal import (
    EpochBlock,
    TemporalModelError,
    assemble_epochs,
)


def _direction(angle):
    return np.array([math.cos(angle), math.sin(angle), 0.0])


@pytest.mark.parametrize("delta", [0.4, 2.4])
def test_equal_curvature_great_circle_midpoint_attains_increment(delta):
    length, curvature = 0.35, 7.0
    original = length * np.array([1.0, 0.0, 0.0])
    # The initial pair is parallel.  Moving each vector by delta/2 in opposite
    # directions achieves the required pair angle, with equal chord costs.
    pair = length * np.array([_direction(-delta / 2), _direction(delta / 2)])
    direct_cost = curvature * np.sum((pair - original) ** 2)
    analytic_cost = 8 * curvature * length**2 * math.sin(delta / 4) ** 2

    np.testing.assert_allclose(np.linalg.norm(pair, axis=1), length, atol=1e-14)
    assert pair[0] @ pair[1] / length**2 == pytest.approx(math.cos(delta), abs=1e-14)
    assert direct_cost == pytest.approx(analytic_cost, rel=2e-14, abs=1e-15)
    assert angle_motion_increment(curvature, curvature, length, delta) == pytest.approx(
        direct_cost, rel=2e-14, abs=1e-15
    )


def test_unequal_curvatures_have_an_analytic_attainable_quarter_turn_cost():
    length, mu1, mu2 = 0.35, 1.0, 3.0
    delta = math.pi / 2
    # Independent one-dimensional optimum: maximize cos(phi)+3*sin(phi).
    phi = math.atan(3.0)
    pair = length * np.array([_direction(-phi), _direction(delta - phi)])
    origin = length * np.array([1.0, 0.0, 0.0])
    direct_cost = mu1 * np.sum((pair[0] - origin) ** 2)
    direct_cost += mu2 * np.sum((pair[1] - origin) ** 2)
    analytic_cost = 2 * length**2 * (4 - math.sqrt(10))

    assert abs(pair[0] @ pair[1]) < 1e-14
    assert direct_cost == pytest.approx(analytic_cost, rel=2e-14)
    assert angle_motion_increment(mu1, mu2, length, delta) == pytest.approx(
        direct_cost, rel=2e-14
    )


def test_zero_angle_pi_and_zero_curvature_limits_are_finite():
    length = 0.35
    assert angle_motion_increment(2.0, 5.0, length, 0.0) == 0.0
    # At pi the less costly vector can turn by pi while the other stays put.
    for mu1, mu2 in [(2.0, 5.0), (5.0, 2.0), (3.0, 3.0)]:
        value = angle_motion_increment(mu1, mu2, length, math.pi)
        assert math.isfinite(value)
        assert value == pytest.approx(4 * length**2 * min(mu1, mu2), rel=2e-14)
    # A zero-curvature vector can absorb the whole angular change at zero cost.
    for mu1, mu2 in [(0.0, 3.0), (3.0, 0.0), (0.0, 0.0)]:
        assert angle_motion_increment(mu1, mu2, length, 0.7) == 0.0
        assert angle_motion_increment(mu1, mu2, length, math.pi) == 0.0


def test_small_angle_with_large_equal_curvature_avoids_cancellation():
    length, curvature, delta = 0.35, 1e24, 1e-12
    # This is the squared chord of an explicit half-angle rotation, not a
    # subtraction of almost equal eigenvalue expressions.
    expected = 8 * curvature * length**2 * math.sin(delta / 4) ** 2
    actual = angle_motion_increment(curvature, curvature, length, delta)
    assert math.isfinite(actual) and actual > 0
    assert actual == pytest.approx(expected, rel=2e-14)


@pytest.mark.parametrize("second_sign", [1.0, -1.0], ids=["parallel", "antiparallel"])
def test_feasible_pair_handles_degenerate_great_circle_choice(second_sign):
    first = np.array([1.0, 0.0, 0.0])
    second = second_sign * first
    length = 0.35
    for beta in [0.0, math.pi / 3, math.pi]:
        pair = feasible_pair(first, second, length, beta, 2.0, 5.0)
        assert np.isfinite(pair).all()
        np.testing.assert_allclose(np.linalg.norm(pair, axis=1), length, rtol=0, atol=1e-14)
        # A dot-product check is independent of the module's vector_angle.
        assert pair[0] @ pair[1] / length**2 == pytest.approx(math.cos(beta), abs=2e-14)


def test_rotation_about_the_baseline_axis_does_not_supply_a_baseline_angle():
    rx90 = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
    constraint = PairMotionConstraint.from_relative_rotation(
        [0.35, 0.0, 0.0], rx90, 0.0, source_id="synthetic_axis_rotation"
    )
    assert constraint.beta_lower_rad == 0.0
    assert constraint.beta_upper_rad == 0.0


@pytest.mark.parametrize(
    "invalid_rotation",
    [
        np.diag([1.0, 1.0, -1.0]),
        np.array([[1.0, 0.1, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
    ],
    ids=["reflection", "nonorthogonal"],
)
def test_relative_rotation_rejects_non_SO3_matrices(invalid_rotation):
    with pytest.raises(TemporalModelError, match=r"SO\(3\)"):
        PairMotionConstraint.from_relative_rotation(
            [0.35, 0.0, 0.0], invalid_rotation, 0.01, source_id="invalid_rotation"
        )


def _zero_center_problem(temporal_covariance=None):
    # Three code and three phase rows per epoch, H=I and lambda=1.
    # For fixed N=0: B'B=2I, bhat=0, Cb=I/2.  Every point on each length
    # sphere has cost 2L^2; any feasible two-vector angle costs exactly 4L^2.
    a = np.vstack([np.zeros((3, 3)), np.eye(3)])
    b = np.vstack([np.eye(3), np.eye(3)])
    blocks = [
        EpochBlock(t, np.zeros(6), a, b, np.eye(6), ("N0", "N1", "N2"))
        for t in [0.0, 0.2]
    ]
    return assemble_epochs(blocks, length_m=0.35, temporal_covariance=temporal_covariance)


def test_pair_evaluator_zero_center_hardcase_has_valid_interval_and_raw_cost():
    problem = _zero_center_problem()
    constraint = PairMotionConstraint(0.4, 0.8, source_id="synthetic_hardcase")
    candidate = PairEvaluator(problem, constraint)(np.zeros(3, dtype=int))
    expected = 4 * 0.35**2

    assert candidate.curvature == (0.0, 0.0)
    assert candidate.extra_motion_lower_bound == 0.0
    assert 0 <= candidate.lower_reduced_cost <= expected + 1e-12
    assert candidate.upper_reduced_cost == pytest.approx(expected, rel=0, abs=1e-12)
    assert candidate.lower_reduced_cost <= candidate.upper_reduced_cost
    assert candidate.upper_reduced_cost - candidate.lower_reduced_cost < 1e-7
    np.testing.assert_allclose(
        np.linalg.norm(candidate.baselines, axis=1), 0.35, rtol=0, atol=1e-14
    )
    cosine = candidate.baselines[0] @ candidate.baselines[1] / 0.35**2
    assert math.cos(0.8) - 1e-13 <= cosine <= math.cos(0.4) + 1e-13

    residual = problem.y - problem.A @ candidate.ambiguity
    residual -= problem.B @ candidate.baselines.reshape(-1)
    direct_raw = float(residual @ np.linalg.solve(problem.Q, residual))
    assert direct_raw == pytest.approx(expected, rel=0, abs=1e-12)
    assert candidate.raw_upper_cost == pytest.approx(direct_raw, rel=0, abs=1e-12)
    assert not candidate.local_refinement_used


def test_pair_evaluator_rejects_cross_epoch_covariance():
    # Valid SPD full Q, with unchanged epoch marginals.  It is outside the
    # independent-epoch bound domain, even though the unconstrained GLS exists.
    full_q = np.block([[np.eye(6), 0.2 * np.eye(6)], [0.2 * np.eye(6), np.eye(6)]])
    problem = _zero_center_problem(temporal_covariance=full_q)
    constraint = PairMotionConstraint(0.0, math.pi, source_id="cross_time_covariance")
    with pytest.raises(TemporalModelError, match="cross-epoch covariance"):
        PairEvaluator(problem, constraint)
