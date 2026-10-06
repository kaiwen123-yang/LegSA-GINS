"""Independent numerical oracles for the carrier solver; no external/native solver.

The small integer domain is bounded by a feasible second-best cost and each
marginal ambiguity variance, so exhaustive coverage is justified, not chosen
after observing a result. Sphere oracle works on each raw fixed-N residual.
"""
from dataclasses import replace
import itertools
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.optimize import brentq

from legsa_gins.paper_rebuild.carrier_phase import solver
from legsa_gins.paper_rebuild.carrier_phase.temporal import (
    EpochBlock, TemporalModelError, assemble_epochs, joint_float, conditional_baselines,
)


def problem_fixture(seed=31):
    rng = np.random.default_rng(seed)
    h = np.array([[.8, -.3, .1], [-.4, .7, .2], [.2, .3, -.9]])
    B = np.vstack([h, h[:2]])
    A = np.vstack([np.zeros((3, 2)), .190293672798365 * np.eye(2)])
    r = rng.normal(size=(5, 5))
    corr = r @ r.T
    corr = corr / np.sqrt(np.diag(corr))[:, None] / np.sqrt(np.diag(corr))[None, :]
    corr = .7 * np.eye(5) + .3 * corr
    std = np.array([.04, .04, .04, .008, .008])
    Q = std[:, None] * corr * std[None, :]
    n = np.array([2, -1])
    blocks = []
    for t, bearing in enumerate([.2, 1.4]):
        direction = np.array([np.cos(bearing), np.sin(bearing), .2])
        b = .35 * direction / np.linalg.norm(direction)
        y = A @ n + B @ b + np.linalg.cholesky(Q) @ rng.normal(size=5)
        blocks.append(EpochBlock(.2*t, y, A, B, Q, ("N0", "N1")))
    return assemble_epochs(blocks)


def direct_float(problem):
    X = np.column_stack([problem.A, problem.B])
    W = np.linalg.inv(problem.Q)
    covariance = np.linalg.inv(X.T @ W @ X)
    estimate = np.linalg.solve(X.T @ W @ X, X.T @ W @ problem.y)
    residual = problem.y - X @ estimate
    return estimate, covariance, float(residual @ W @ residual)


def direct_sphere(center_rhs, weight, length):
    # Independent Lagrange-multiplier root for positive-definite quadratic;
    # our seeded oracle cases have nonzero projection on the minimum eigenspace.
    eigen, U = np.linalg.eigh(weight)
    beta = U.T @ center_rhs
    def norm_error(multiplier):
        return np.sum((beta / (eigen + multiplier))**2) - length**2
    low = np.nextafter(-eigen[0], np.inf)
    assert norm_error(low) > 0  # excludes exact trust-region hard cases in this fixture
    high = max(1., eigen[-1])
    while norm_error(high) > 0:
        high *= 2
    mu = brentq(norm_error, low, high, xtol=1e-12, rtol=1e-14)
    return U @ (beta / (eigen + mu))


def direct_fixed_integer(problem, n):
    result = []
    cost = 0
    for k, (rows, cols) in enumerate(zip(problem.row_slices, problem.baseline_slices)):
        v = problem.y[rows] - problem.A[rows] @ n
        B = problem.B[rows, cols]
        W = np.linalg.inv(problem.Q[rows, rows])
        b = direct_sphere(B.T @ W @ v, B.T @ W @ B, problem.lengths[k])
        residual = v - B @ b
        cost += float(residual @ W @ residual)
        result.append(b)
    return cost, np.array(result)


def exhaustive_global_pair(problem):
    estimate, covariance, float_cost = direct_float(problem)
    feasible = [np.array([2, -1]), np.array([3, -1])]
    limit = max(direct_fixed_integer(problem, n)[0] for n in feasible)
    width = np.sqrt(np.maximum(0., limit-float_cost) * np.diag(covariance)[:2])
    ranges = [range(int(np.ceil(c-w-1e-10)), int(np.floor(c+w+1e-10))+1)
              for c, w in zip(estimate[:2], width)]
    assert np.prod([len(r) for r in ranges]) < 1000
    all_values = []
    for n in itertools.product(*ranges):
        cost, baselines = direct_fixed_integer(problem, np.array(n))
        all_values.append((cost, n, baselines))
    all_values.sort(key=lambda x: (x[0], x[1]))
    assert len(all_values) >= 2
    return all_values[:2]


def fake_lambda_bridge(transform):
    # Search is exercised independently of RTKLIB seed selection/decorrelation.
    # Deliberately poor seeds force traversal. Transform is exact unimodular.
    class Bridge:
        def __init__(self, _):
            pass
        def candidates(self, mean, covariance, count):
            return [SimpleNamespace(ambiguity=np.array([4, -3])),
                    SimpleNamespace(ambiguity=np.array([0, 1]))]
        def decorrelate(self, mean, covariance):
            return SimpleNamespace(transformation=transform,
                                   float_ambiguity=transform.T @ mean,
                                   covariance=transform.T @ covariance @ transform)
    return Bridge


@pytest.mark.parametrize("seed", [31, 39])
@pytest.mark.parametrize("transform", [np.eye(2, dtype=int), np.array([[1, 2], [0, 1]])])
def test_certified_global_pair_matches_independent_raw_residual_oracle(monkeypatch, seed, transform):
    problem = problem_fixture(seed)
    oracle = exhaustive_global_pair(problem)
    monkeypatch.setattr(solver, "RTKLIBLambdaBridge", fake_lambda_bridge(transform))
    answer = solver.solve_temporal(problem, "NO_NATIVE_LIBRARY", initial_candidates=2,
                                   timeout_s=10, node_limit=10000)
    assert answer.global_optimum_certified
    assert answer.certificate.expanded_nodes > 0
    for candidate, expected in zip([answer.best, answer.second], oracle):
        assert tuple(candidate.ambiguity) == expected[1]
        assert candidate.full_residual_cost == pytest.approx(expected[0], rel=1e-8, abs=1e-8)
        assert np.max(np.abs(candidate.baselines-expected[2])) < 1e-7


@pytest.mark.parametrize("correlation", [0., .6])
def test_joint_float_and_conditional_baselines_match_direct_gls(correlation):
    independent = problem_fixture()
    cross = np.kron([[1., correlation], [correlation, 1.]], independent.Q[:5, :5])
    problem = replace(independent, Q=cross)
    f = joint_float(problem)
    estimate, covariance, cost = direct_float(problem)
    assert np.max(np.abs(np.r_[f.ambiguity, f.baseline]-estimate)) < 1e-9
    assert np.max(np.abs(f.covariance-covariance)) < 1e-10
    assert f.residual_objective == pytest.approx(cost, abs=1e-10)
    fixed = np.array([3., -2.])
    W = np.linalg.inv(problem.Q)
    direct = np.linalg.solve(problem.B.T @ W @ problem.B,
                             problem.B.T @ W @ (problem.y-problem.A @ fixed))
    assert np.max(np.abs(conditional_baselines(f, fixed).ravel()-direct)) < 1e-10
    expected_cov = np.linalg.inv(problem.B.T @ W @ problem.B)
    assert np.max(np.abs(f.conditional_covariance_b-expected_cov)) < 1e-11
    if correlation:
        with pytest.raises(TemporalModelError, match="cross-epoch"):
            solver.evaluate_integer(problem, f, [2, -1])


def test_tiny_budget_does_not_turn_poor_seed_into_certified_solution(monkeypatch):
    monkeypatch.setattr(solver, "RTKLIBLambdaBridge", fake_lambda_bridge(np.eye(2, dtype=int)))
    result = solver.solve_temporal(problem_fixture(), "NO_NATIVE_LIBRARY",
                                   initial_candidates=2, node_limit=1, timeout_s=5)
    assert not result.global_optimum_certified
    assert not result.candidate_available
    assert result.certificate.termination_reason == "NODE_LIMIT"


def test_oversize_integer_is_rejected_not_silently_wrapped():
    p = problem_fixture()
    with pytest.raises(TemporalModelError, match="integer|represent|range|exact"):
        solver.evaluate_integer(p, joint_float(p), [2**63, -1])


def historical_arc_problem():
    base = problem_fixture(43)
    rows0, rows1 = base.row_slices
    blocks = [
        EpochBlock(0., base.y[rows0], base.A[rows0], base.B[rows0, :3], base.Q[rows0, rows0], ("OLD", "SHARED")),
        EpochBlock(.2, base.y[rows1] + base.A[rows1, 0], base.A[rows1],
                   base.B[rows1, 3:6], base.Q[rows1, rows1], ("NEW", "SHARED")),
    ]
    return assemble_epochs(blocks)


def independent_active_class_pair(problem, active_indices):
    estimate, covariance, float_cost = direct_float(problem)
    feasible = [np.array([2, -1, 3]), np.array([2, -1, 4])]
    upper = max(direct_fixed_integer(problem, n)[0] for n in feasible)
    width = np.sqrt(np.maximum(0., upper-float_cost) * np.diag(covariance)[:3])
    ranges = [range(int(np.ceil(c-w-1e-10)), int(np.floor(c+w+1e-10))+1)
              for c,w in zip(estimate[:3],width)]
    assert np.prod([len(r) for r in ranges]) < 10000
    classes = {}
    for values in itertools.product(*ranges):
        n = np.array(values)
        cost, b = direct_fixed_integer(problem, n)
        key = tuple(values[i] for i in active_indices)
        if key not in classes or cost < classes[key][0]:
            classes[key] = (cost, values, b)
    return sorted(classes.values(), key=lambda x:(x[0],x[1]))[:2]


@pytest.mark.parametrize("transform", [np.eye(3, dtype=int), np.array([[1,2,0],[0,1,1],[0,0,1]])])
def test_active_class_certificate_profiles_all_historical_integer_values(monkeypatch, transform):
    problem = historical_arc_problem()
    class Bridge:
        def __init__(self, _): pass
        def candidates(self, mean, covariance, count):
            # Both seeds belong to the same active NEW/SHARED class.
            return [SimpleNamespace(ambiguity=np.array([1,-1,3])),
                    SimpleNamespace(ambiguity=np.array([3,-1,3]))]
        def decorrelate(self, mean, covariance):
            return SimpleNamespace(transformation=transform,
                float_ambiguity=transform.T@mean, covariance=transform.T@covariance@transform)
    monkeypatch.setattr(solver,"RTKLIBLambdaBridge",Bridge)
    oracle = independent_active_class_pair(problem, (2,1))
    answer = solver.solve_temporal(problem,"NO_NATIVE_LIBRARY",initial_candidates=2,
        node_limit=10000, timeout_s=10., distinct_ambiguity_labels=("NEW","SHARED"))
    assert answer.global_optimum_certified
    assert answer.certificate.certificate_scope=="two_best_selected_integer_classes"
    assert answer.certificate.distinct_ambiguity_labels==("NEW","SHARED")
    assert answer.best.ambiguity.shape==(3,)  # OLD nuisance never removed
    assert tuple(answer.best.ambiguity[[2,1]])!=tuple(answer.second.ambiguity[[2,1]])
    for actual, expected in zip((answer.best,answer.second),oracle):
        assert tuple(actual.ambiguity)==expected[1]
        assert actual.full_residual_cost==pytest.approx(expected[0],abs=1e-8)
        assert np.max(abs(actual.baselines-expected[2]))<1e-7
