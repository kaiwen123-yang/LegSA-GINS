"""One numerical check of separator correlation and checkpoint reconstruction."""

import gtsam
import numpy as np

from legsa_gins.paper_rebuild.joint_navigation.window import JointWindow


def test_separator_and_checkpoint_match_full_three_state_graph():
    unit = gtsam.noiseModel.Isotropic.Sigma(1, 1.0)
    factors = [
        gtsam.PriorFactorDouble(0, 0.0, unit),
        gtsam.BetweenFactorDouble(0, 1, 1.0, unit),
        gtsam.BetweenFactorDouble(0, 2, 2.0, unit),
        gtsam.BetweenFactorDouble(1, 2, 1.0, unit),
        gtsam.PriorFactorDouble(2, 2.6, unit),
    ]
    initial = gtsam.Values()
    for key in (0, 1, 2):
        initial.insert(key, 0.0)
    full_graph = JointWindow._graph(factors)
    full = gtsam.LevenbergMarquardtOptimizer(full_graph, initial).optimize()
    window = JointWindow(lag_s=1.0)
    window.update(factors, initial, {0: 0.0, 1: 1.0, 2: 2.0}, 2.0)
    assert window.last_marginalized == (0,)
    assert set(window.values.keys()) == {1, 2}
    np.testing.assert_allclose(
        [window.values.atDouble(k) for k in (1, 2)],
        [full.atDouble(k) for k in (1, 2)], atol=1e-8,
    )
    keys = gtsam.KeyVector([1, 2])
    expected_cov = gtsam.Marginals(full_graph, full).jointMarginalCovariance(keys).fullMatrix()
    actual_cov = gtsam.Marginals(window.graph, window.values).jointMarginalCovariance(keys).fullMatrix()
    assert abs(expected_cov[0, 1]) > 0.1
    np.testing.assert_allclose(actual_cov, expected_cov, atol=1e-10)
    np.testing.assert_allclose(window.error(), full_graph.error(full), atol=1e-10)

    # Pollute both the estimate and a later marginal prior, then restore the
    # earlier checkpoint and consume only the independently valid observation.
    checkpoint = window.snapshot()
    wrong = gtsam.PriorFactorDouble(1, -2.0, gtsam.noiseModel.Isotropic.Sigma(1, 0.2))
    window.update([wrong], gtsam.Values(), {}, 3.0)
    assert not window.values.exists(1)
    assert abs(window.values.atDouble(2) - full.atDouble(2)) > 0.1
    window.restore(checkpoint)
    np.testing.assert_allclose(window.values.atDouble(2), full.atDouble(2), atol=1e-8)
    valid = gtsam.PriorFactorDouble(2, 2.2, gtsam.noiseModel.Isotropic.Sigma(1, 0.4))
    window.update([valid], gtsam.Values(), {}, 3.0)
    full_graph.push_back(valid)
    oracle = gtsam.LevenbergMarquardtOptimizer(full_graph, full).optimize()
    np.testing.assert_allclose(window.values.atDouble(2), oracle.atDouble(2), atol=1e-8)
    np.testing.assert_allclose(
        window.covariance(2),
        gtsam.Marginals(full_graph, oracle).marginalCovariance(2), atol=1e-10,
    )
    np.testing.assert_allclose(window.error(), full_graph.error(oracle), atol=1e-10)
    # The saved checkpoint itself was not mutated by either continuation.
    assert set(checkpoint.values.keys()) == {1, 2}
    np.testing.assert_allclose(checkpoint.values.atDouble(2), full.atDouble(2), atol=1e-8)
    window.restore(checkpoint)
    window.update([], gtsam.Values(), {}, 3.0, retain_keys={1})
    assert window.values.exists(1)


def test_constrained_elimination_retains_inconsistent_prior_cost():
    """Zero-RW equalities must not erase a hypothesis's irreducible cost."""
    unit = gtsam.noiseModel.Isotropic.Sigma(1, 1.)
    equal = gtsam.noiseModel.Constrained.All(1)
    factors = [gtsam.PriorFactorDouble(0, 0., unit),
               gtsam.PriorFactorDouble(0, 2., unit),
               gtsam.BetweenFactorDouble(0, 1, 0., equal)]
    initial = gtsam.Values()
    initial.insert(0, 0.)
    initial.insert(1, 0.)
    full_graph = JointWindow._graph(factors)
    full = gtsam.LevenbergMarquardtOptimizer(full_graph, initial).optimize()
    window = JointWindow(lag_s=.5)
    window.update(factors, initial, {0: 0., 1: 1.}, 1.)
    np.testing.assert_allclose(window.objective_offset, 1., atol=1e-10)
    np.testing.assert_allclose(window.error(), full_graph.error(full), atol=1e-10)
    checkpoint = window.snapshot()

    later = [gtsam.BetweenFactorDouble(1, 2, 0., equal),
             gtsam.PriorFactorDouble(2, 2., unit)]
    new_value = gtsam.Values()
    new_value.insert(2, window.values.atDouble(1))
    window.update(later, new_value, {2: 2.}, 2.)
    for factor in later:
        full_graph.push_back(factor)
    full.insert(2, 1.)
    oracle = gtsam.LevenbergMarquardtOptimizer(full_graph, full).optimize()
    np.testing.assert_allclose(window.values.atDouble(2), oracle.atDouble(2), atol=1e-8)
    np.testing.assert_allclose(window.error(), full_graph.error(oracle), atol=1e-9)
    np.testing.assert_allclose(window.error(), 4./3., atol=1e-9)
    window.restore(checkpoint)
    np.testing.assert_allclose(window.objective_offset, 1., atol=1e-10)
    np.testing.assert_allclose(window.error(), 1., atol=1e-10)


if __name__ == "__main__":
    test_separator_and_checkpoint_match_full_three_state_graph()
    test_constrained_elimination_retains_inconsistent_prior_cost()
    print("PASS: separator covariance, constrained objective constants, checkpoint restore and retained key")


def test_square_root_separator_keeps_weak_anchor_beside_strong_transition():
    # H-based Schur subtraction loses the unit prior next to 1e18 transition
    # information. Local QR must retain that prior, without an artificial floor.
    factors = [gtsam.PriorFactorDouble(0, 0., gtsam.noiseModel.Isotropic.Sigma(1, 1.)),
               gtsam.BetweenFactorDouble(0, 1, 0., gtsam.noiseModel.Isotropic.Sigma(1, 1e-9))]
    values = gtsam.Values(); values.insert(0, 0.); values.insert(1, 0.)
    window = JointWindow(lag_s=.05)
    window.update(factors, values, {0: 0., 1: .1}, .1)
    assert window.last_marginalized == (0,)
    linear = window.graph.linearize(window.values)
    assert all(isinstance(linear.at(i), gtsam.JacobianFactor) for i in range(linear.size()))
    np.testing.assert_allclose(window.covariance(1), [[1.]], atol=1e-12, rtol=1e-12)
    restored = JointWindow(lag_s=.05); restored.restore(window.snapshot())
    np.testing.assert_allclose(restored.covariance(1), [[1.]], atol=1e-12, rtol=1e-12)
