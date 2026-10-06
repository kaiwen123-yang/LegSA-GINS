"""Factor reuse and pruning regressions; synthetic inputs, no native calls.

The existing independent raw-residual/exhaustive suite tests mathematical
correctness. These tests isolate the optimization: centers/radii are not cached,
cache setup is bounded, and early rejection cannot change retained tree nodes.
"""
from dataclasses import asdict, FrozenInstanceError
from types import SimpleNamespace
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase import solver
from legsa_gins.paper_rebuild.carrier_phase.temporal import joint_float
from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import (
    BaselineSphereMetric, CLambdaError, constrained_baseline,
)
from test_carrier_solver_review import problem_fixture, fake_lambda_bridge


@pytest.mark.parametrize("covariance", [
    np.eye(3), np.diag([.25, 1., 4.]),
    np.diag([1., 1.+1e-12, 3.]),
    np.array([[.04, .003, 0.], [.003, .02, .001], [0., .001, .08]]),
])
def test_metric_reuses_factors_but_not_center_or_radius(monkeypatch, covariance):
    cases = [(np.array(c), length) for c, length in [
        ([0., 0., 0.], .35), ([0., 0., 1e-12], .35),
        ([0., 0., -1e-12], .35), ([.8, 0., 0.], .35),
        ([.2, -.4, .1], .7), ([.35, 0., 0.], .35),
    ]]
    expected = [constrained_baseline(c, covariance, length) for c, length in cases]
    calls = {"inv": 0, "eigh": 0}
    for name in calls:
        original = getattr(np.linalg, name)
        def counted(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(np.linalg, name, counted)
    metric = BaselineSphereMetric.from_covariance(covariance)
    for (center, length), wanted in zip(cases, expected):
        actual = metric.solve(center, length)
        np.testing.assert_array_equal(actual.baseline, wanted.baseline)
        for field in ("objective", "lagrange_multiplier", "constraint_error_m", "hard_case"):
            assert getattr(actual, field) == getattr(wanted, field)
    assert calls == {"inv": 1, "eigh": 1}


def test_metric_owns_readonly_covariance_factors():
    q = np.diag([.25, 1., 4.])
    metric = BaselineSphereMetric.from_covariance(q)
    wanted = metric.solve([.2, -.1, .4], .35)
    q[:] = np.nan
    actual = metric.solve([.2, -.1, .4], .35)
    np.testing.assert_array_equal(actual.baseline, wanted.baseline)
    for array in (metric.weight, metric.eigenvalues, metric.vectors, metric.minimum_mask):
        assert not array.flags.writeable
        with pytest.raises(ValueError):
            array.flat[0] = 0
    with pytest.raises(FrozenInstanceError):
        metric.minimum = 0


def test_cached_hard_case_preserves_exact_minimum_eigenspace_and_tiny_sign():
    metric = BaselineSphereMetric.from_covariance(np.diag([.25, 1., 4.]))
    zero = metric.solve([0., 0., 0.], .35)
    assert zero.hard_case
    assert zero.objective == pytest.approx(.35**2/4., abs=1e-16)
    for tiny in (-1e-12, 1e-12):
        actual = metric.solve([0., 0., tiny], .35)
        assert not actual.hard_case
        assert np.sign(actual.baseline[2]) == np.sign(tiny)
        np.testing.assert_allclose(actual.baseline, [0., 0., np.sign(tiny)*.35], atol=1e-14)
    # Near-equal eigenvalues are still distinct. The true minimum direction
    # carries a nonzero projection and must not be classified as a hard case.
    metric = BaselineSphereMetric.from_covariance(np.diag([1., 1.+1e-12, .5]))
    actual = metric.solve([0., -1e-12, 0.], .35)
    assert not actual.hard_case and actual.baseline[1] < 0


@pytest.mark.parametrize("center,q,length,match", [
    ([0., 0.], np.eye(3), .35, "invalid constrained-baseline"),
    ([np.nan, 0., 0.], np.eye(3), .35, "invalid constrained-baseline"),
    ([0., 0., 0.], np.eye(3), 0., "invalid constrained-baseline"),
    ([0., 0., 0.], np.eye(3), np.inf, "invalid constrained-baseline"),
    ([0., 0.], -np.eye(3), 0., "positive definite"),
    ([0., 0., 0.], np.full((3, 3), np.nan), .35, "finite square"),
])
def test_public_sphere_validation_order_and_domains(center, q, length, match):
    with pytest.raises(CLambdaError, match=match):
        constrained_baseline(center, q, length)


def bound_fixture():
    problem = problem_fixture()
    floating = joint_float(problem)
    reduced = SimpleNamespace(transformation=np.eye(2),
        covariance=floating.covariance_aa, float_ambiguity=floating.ambiguity)
    return solver._BaselineBoundCache(problem, floating, reduced)


def original_node_bound(cache, suffix, ambiguity):
    # The pre-optimization bound: the same marginal metric, freshly factored,
    # and no cheap preprune. It is not an alternate scientific objective.
    indices, gain, cov, maximum_eigenvalues = cache.parameters(len(suffix))
    center = cache.floating.baseline + gain @ (
        np.asarray(suffix, float)-cache.reduced.float_ambiguity[indices])
    cheap = np.array([(np.linalg.norm(center[ss])-cache.problem.lengths[k])**2
        for k, ss in enumerate(cache.problem.baseline_slices)]) / maximum_eigenvalues
    k = int(np.argmax(cheap))
    ss = cache.problem.baseline_slices[k]
    exact = constrained_baseline(center[ss], cov[ss,ss], cache.problem.lengths[k]).objective
    return float(ambiguity+max(float(np.max(cheap)), exact)), float(ambiguity+np.max(cheap))


def test_cheap_prune_skips_sphere_only_strictly_above_same_cutoff():
    cache = bound_fixture()
    exact, cheap = original_node_bound(cache, (13,), 1.25)
    assert cheap > 0 and exact >= cheap
    cutoff = np.nextafter(cheap, -np.inf)
    assert cache((13,), 1.25, cutoff=cutoff) == cheap
    assert cache.cheap_prunes == 1 and cache.sphere_evaluations == 0
    assert not cache.sphere_metrics  # even factor setup is skipped
    # Equality cannot be discarded by the optimization. Existing exact-bound
    # pruning still decides whether this node can enter the frontier.
    assert cache((13,), 1.25, cutoff=cheap) == exact
    assert cache.sphere_evaluations == 1


def test_depth_metrics_are_reused_and_unpruned_bound_is_unchanged(monkeypatch):
    cache = bound_fixture()
    nodes = [((), 0.), ((-1,), .2), ((2, -1), 3.), ((-7,), 8.), ((3, 4), 2.)]
    expected = [original_node_bound(cache, suffix, amb)[0] for suffix, amb in nodes]
    for (suffix, amb), wanted in zip(nodes, expected):
        assert cache(suffix, amb) == wanted
    assert cache.sphere_evaluations == len(nodes)
    factor_count = len(cache.sphere_metrics)
    def forbidden(*args, **kwargs):
        raise AssertionError("cached depth/epoch metric was refactored")
    monkeypatch.setattr(np.linalg, "inv", forbidden)
    monkeypatch.setattr(np.linalg, "eigh", forbidden)
    for (suffix, amb), wanted in zip(nodes, expected):
        assert cache(suffix, amb) == wanted
    assert len(cache.sphere_metrics) == factor_count


def test_leaf_covariance_factors_are_reused_without_dropping_full_residual_check(monkeypatch):
    problem = problem_fixture()
    floating = joint_float(problem)
    values = [np.array([2, -1]), np.array([3, -1]), np.array([-1, 2])]
    expected = [solver.evaluate_integer(problem, floating, n) for n in values]
    evaluator = solver._IntegerEvaluator(problem, floating)
    def forbidden(*args, **kwargs):
        raise AssertionError("constant leaf covariance was refactored")
    monkeypatch.setattr(np.linalg, "inv", forbidden)
    monkeypatch.setattr(np.linalg, "eigh", forbidden)
    for n, wanted in zip(values, expected):
        actual = evaluator(n)
        np.testing.assert_array_equal(actual.baselines, wanted.baselines)
        assert actual.full_residual_cost == wanted.full_residual_cost
        assert actual.reduced_cost == wanted.reduced_cost
        assert actual.objective_identity_error == wanted.objective_identity_error
    assert evaluator.sphere_evaluations == len(values)*problem.epoch_count


@pytest.mark.parametrize("seed", [31, 39])
@pytest.mark.parametrize("transform", [np.eye(2, dtype=int), np.array([[1, 2], [0, 1]])])
def test_complete_tree_matches_uncached_no_preprune_path(monkeypatch, seed, transform):
    problem = problem_fixture(seed)
    monkeypatch.setattr(solver, "RTKLIBLambdaBridge", fake_lambda_bridge(transform))
    optimized = solver.solve_temporal(problem, "NO_NATIVE_LIBRARY", initial_candidates=2,
        timeout_s=10, node_limit=10000)
    original_cache = solver._BaselineBoundCache
    class NoPreprune(original_cache):
        def __call__(self, suffix, ambiguity_bound, *, cutoff=np.inf):
            return super().__call__(suffix, ambiguity_bound)  # ignore cutoff
    class OneShotMetric:
        def __init__(self, covariance): self.covariance = covariance.copy()
        def solve(self, center, length):
            return constrained_baseline(center, self.covariance, length)
    monkeypatch.setattr(solver, "_BaselineBoundCache", NoPreprune)
    monkeypatch.setattr(BaselineSphereMetric, "from_covariance", OneShotMetric)
    uncached = solver.solve_temporal(problem, "NO_NATIVE_LIBRARY", initial_candidates=2,
        timeout_s=10, node_limit=10000)
    assert optimized.global_optimum_certified and uncached.global_optimum_certified
    for actual, wanted in zip((optimized.best, optimized.second), (uncached.best, uncached.second)):
        np.testing.assert_array_equal(actual.ambiguity, wanted.ambiguity)
        np.testing.assert_array_equal(actual.baselines, wanted.baselines)
        assert actual.reduced_cost == wanted.reduced_cost
        assert actual.full_residual_cost == wanted.full_residual_cost
    omit = {"elapsed_s", "cheap_bound_prunes", "bound_sphere_evaluations", "sphere_metric_factorizations"}
    a, b = asdict(optimized.certificate), asdict(uncached.certificate)
    assert {k:v for k,v in a.items() if k not in omit} == {k:v for k,v in b.items() if k not in omit}
    assert a["bound_evaluations"] == a["bound_sphere_evaluations"]+a["cheap_bound_prunes"]
    assert a["bound_sphere_evaluations"] <= b["bound_sphere_evaluations"]
