"""One linear conditional/reconstruction check, including an exact coordinate."""

import gtsam
import numpy as np
from unittest.mock import patch
import time

from legsa_gins.paper_rebuild.joint_navigation.window import (
    JointWindow, key_ordering, eliminate_qr, conditional_joint_covariance)


def linear_measurement(coefficients, observation, noise):
    keys = tuple(coefficients)

    def error(_factor, values, jacobians):
        if jacobians is not None:
            for index, key in enumerate(keys):
                jacobians[index] = np.array([[coefficients[key]]], order="F")
        return np.array([sum(coefficients[key] * values.atDouble(key) for key in keys) - observation])

    return gtsam.CustomFactor(noise, gtsam.KeyVector(list(keys)), error)


def values_at(mapping):
    values = gtsam.Values()
    for key, value in mapping.items():
        values.insert(key, float(value))
    return values


def independent_full_qr(factors, anchor):
    """Dense all-variable QR oracle; no fixed-lag or local-elimination helper."""
    graph = JointWindow._graph(factors)
    order = key_ordering(sorted(anchor.keys()))
    conditional, _ = gtsam.JacobianFactor(graph.linearize(anchor), order).eliminate(order)
    result = anchor.retract(conditional.solve(gtsam.VectorValues()))
    root = np.linalg.solve(conditional.R(), np.diag(conditional.get_model().sigmas()))
    return result, root @ root.T, float(graph.error(result))


@patch("gtsam.LevenbergMarquardtOptimizer",
       side_effect=AssertionError("Gaussian conditional invoked a nonlinear optimizer"))
def test_shared_anchor_conditionals_match_independent_history_qr(_nonlinear_optimizer):
    # x0,x1,x2 share an external anchor. u is common foot translation; v=u
    # is an exact coordinate alias. Fixed and released models differ only in
    # whether u is constrained, not in observation noise or physical data.
    prior = gtsam.noiseModel.Isotropic.Sigma(1, 1.)
    motion = gtsam.noiseModel.Isotropic.Sigma(1, .2)
    foot = gtsam.noiseModel.Isotropic.Sigma(1, .3)
    receiver = gtsam.noiseModel.Isotropic.Sigma(1, .4)
    exact = gtsam.noiseModel.Constrained.All(1)
    base = [gtsam.PriorFactorDouble(0, .1, prior),
            gtsam.BetweenFactorDouble(0, 1, 1., motion),
            gtsam.BetweenFactorDouble(1, 2, 1., motion),
            gtsam.PriorFactorDouble(2, 2.1, receiver),
            linear_measurement({0: 1., 3: 1.}, .4, foot),
            linear_measurement({1: 1., 4: 1.}, 1.7, foot),
            linear_measurement({2: 1., 3: 1.}, 2.5, foot),
            linear_measurement({3: -1., 4: 1.}, 0., exact)]
    first_anchor = values_at({0: 5., 1: -3., 2: 10., 3: .7, 4: .7})

    means = []
    for fixed in (True, False):
        factors = base + ([gtsam.PriorFactorDouble(3, 0., exact)] if fixed else [])
        oracle, covariance, objective = independent_full_qr(factors, first_anchor)
        window = JointWindow(lag_s=1.)
        window.update(factors, gtsam.Values(first_anchor),
                      {0: 0., 1: 1., 2: 2., 3: 2., 4: 2.}, 2.,
                      gaussian_only=True, linearization_values=first_anchor)
        keys = [1, 2, 3, 4]
        assert window.gaussian_only and window.last_marginalized == (0,)
        np.testing.assert_allclose([window.values.atDouble(k) for k in keys],
                                   [oracle.atDouble(k) for k in keys], atol=2e-13)
        np.testing.assert_allclose(window.joint_covariance(keys),
                                   covariance[np.ix_(keys, keys)], atol=2e-13)
        np.testing.assert_allclose(window.error(), objective, atol=2e-12)
        np.testing.assert_allclose(window.values.atDouble(3), window.values.atDouble(4), atol=2e-13)
        assert window.linearization_values.atDouble(1) == -3.
        checkpoint = window.snapshot()

        later = [gtsam.BetweenFactorDouble(2, 5, 1., motion),
                 gtsam.PriorFactorDouble(5, 3.3, receiver),
                 linear_measurement({5: 1., 3: 1.}, 3.9, foot)]
        second_anchor = values_at({0: 7., 1: 2., 2: 3., 3: -.2, 4: -.2, 5: 5.})
        window.update(later, values_at({5: 0.}), {5: 3.}, 3., retain_keys={3, 4},
                      gaussian_only=True, linearization_values=second_anchor)
        oracle, covariance, objective = independent_full_qr(factors + later, second_anchor)
        keys = [2, 3, 4, 5]
        np.testing.assert_allclose([window.values.atDouble(k) for k in keys],
                                   [oracle.atDouble(k) for k in keys], atol=2e-13)
        np.testing.assert_allclose(window.joint_covariance(keys),
                                   covariance[np.ix_(keys, keys)], atol=2e-13)
        np.testing.assert_allclose(window.error(), objective, atol=2e-12)
        means.append(window.values.atDouble(5))

        window.restore(checkpoint)
        assert window.gaussian_only and window.linearization_values.atDouble(1) == -3.
        np.testing.assert_allclose(window.error(), independent_full_qr(factors, first_anchor)[2], atol=2e-12)
    assert abs(means[0] - means[1]) > .05


def test_qr_rotation_mean_beyond_pi_survives_exact_constraint_and_restore():
    pose_key, alias_key = 10, 20
    anchor = gtsam.Values()
    anchor.insert(pose_key, gtsam.Pose3())
    anchor.insert(alias_key, 0.)
    target = np.array([0., 0., 4., 1., 2., 3.])
    pose = gtsam.JacobianFactor(pose_key, np.eye(6), target,
                                gtsam.noiseModel.Isotropic.Sigma(6, 1.))
    exact = gtsam.JacobianFactor(pose_key, np.array([[0., 0., -1., 0., 0., 0.]]),
                                 alias_key, np.ones((1, 1)), np.zeros(1),
                                 gtsam.noiseModel.Constrained.All(1))
    factors = [gtsam.LinearContainerFactor(factor, anchor) for factor in (pose, exact)]
    window = JointWindow(lag_s=10.)
    window.update(factors, gtsam.Values(anchor), {pose_key: 1., alias_key: 0.}, 1.,
                  gaussian_only=True, linearization_values=anchor)
    np.testing.assert_allclose(window.linearization_delta.at(pose_key), target, atol=1e-13)
    np.testing.assert_allclose(window.linearization_delta.at(alias_key), [4.], atol=1e-13)
    assert abs(anchor.localCoordinates(window.values).at(pose_key)[2] - 4.) > 6.
    np.testing.assert_allclose(window.error(), 0., atol=1e-25)
    checkpoint = window.snapshot()

    window.lag_s = .5
    window.update([], gtsam.Values(), {}, 1., gaussian_only=True)
    assert window.last_marginalized == (alias_key,)
    assert not window.linearization_delta.exists(alias_key)
    np.testing.assert_allclose(window.linearization_delta.at(pose_key), target, atol=1e-13)
    np.testing.assert_allclose(window.joint_covariance([pose_key]), np.eye(6), atol=1e-13)
    np.testing.assert_allclose(window.error(), 0., atol=1e-25)
    window.restore(checkpoint)
    np.testing.assert_allclose(window.linearization_delta.at(pose_key), target, atol=1e-13)
    np.testing.assert_allclose(window.linearization_delta.at(alias_key), [4.], atol=1e-13)
    np.testing.assert_allclose(window.error(), 0., atol=1e-25)


def conditional_chain(chain_length):
    """An anisotropic vector chain with an exact, reordered coordinate alias."""
    keys = [10000 - 37 * j for j in range(chain_length)]
    alias = 7
    anchor = gtsam.Values()
    for j, key in enumerate(keys):
        anchor.insert_vector(key, np.array([.03*j, -.02*j]))
    anchor.insert_vector(alias, np.zeros(2))
    factors = [gtsam.JacobianFactor(keys[0], np.eye(2), np.array([.2, -.3]),
                                   gtsam.noiseModel.Diagonal.Sigmas(np.array([1.7, .6])))]
    for j, (before, after) in enumerate(zip(keys, keys[1:]), 1):
        factors.append(gtsam.JacobianFactor(before, np.array([[-1., -.08], [.04, -.95]]),
            after, np.eye(2), np.array([.1, -.05]),
            gtsam.noiseModel.Diagonal.Sigmas(np.array([.03, .2]))))
    factors.append(gtsam.JacobianFactor(keys[2], -2.*np.eye(2), alias, np.eye(2), np.zeros(2),
                                        gtsam.noiseModel.Constrained.All(2)))
    window = JointWindow(lag_s=100.)
    window.update([gtsam.LinearContainerFactor(factor, anchor) for factor in factors],
                  gtsam.Values(anchor), {**{key: j*.1 for j, key in enumerate(keys)}, alias: 1.},
                  (chain_length-1)*.1, gaussian_only=True, linearization_values=anchor)
    return window, keys, alias


def independently_reeliminated_covariance(window, keys):
    """Reference recomputes QR from saved Jacobian rows, not saved conditionals."""
    linear = JointWindow._linear_graph(window._linear_factors)
    ordering = gtsam.Ordering.ColamdConstrainedLastGaussianFactorGraph(linear, keys, True)
    query = set(keys)
    eliminated = [ordering.at(i) for i in range(ordering.size()) if ordering.at(i) not in query]
    _, remaining = eliminate_qr(linear, eliminated)
    conditional, _ = gtsam.JacobianFactor(remaining, key_ordering(keys)).eliminate(key_ordering(keys))
    root = np.linalg.solve(conditional.R(), np.diag(conditional.get_model().sigmas()))
    return root @ root.T


def test_saved_qr_queries_keep_units_cross_covariance_and_lifecycle():
    # Work directly with unwhitened Gaussian rows so non-unit sigmas survive
    # inside the actual conditionals. LinearContainerFactor linearization can
    # whiten these to unit sigmas before the window's QR sees them.
    raw = gtsam.GaussianFactorGraph()
    raw.push_back(gtsam.JacobianFactor(9, np.ones((1, 1)), np.zeros(1),
                                       gtsam.noiseModel.Isotropic.Sigma(1, 2.)))
    raw.push_back(gtsam.JacobianFactor(9, -2.*np.ones((1, 1)), 3, np.ones((1, 1)), np.zeros(1),
                                       gtsam.noiseModel.Constrained.All(1)))
    net, _ = eliminate_qr(raw, [9, 3])
    np.testing.assert_allclose([net.at(0).get_model().sigmas()[0], net.at(1).get_model().sigmas()[0]], [0., 4.])
    np.testing.assert_allclose(conditional_joint_covariance(net, {9: 1, 3: 1}, [3, 9]),
                               [[16., 8.], [8., 4.]], atol=1e-13)
    window, states, alias = conditional_chain(12)
    saved = window._gaussian_conditionals
    sigmas = np.concatenate([saved.at(i).get_model().sigmas() for i in range(saved.size())])
    assert np.any(sigmas == 0.)
    queries = [[alias, states[2]], [states[-1], alias, states[-2]]]
    expected = [independently_reeliminated_covariance(window, keys) for keys in queries]
    with patch("legsa_gins.paper_rebuild.joint_navigation.window.eliminate_qr",
               side_effect=AssertionError("a cached covariance query repeated QR")):
        for keys, covariance in zip(queries, expected):
            np.testing.assert_allclose(window.joint_covariance(keys), covariance, atol=2e-12, rtol=2e-12)
    exact_covariance = expected[0]
    contrast = np.c_[np.eye(2), -2.*np.eye(2)]
    np.testing.assert_allclose(contrast @ exact_covariance @ contrast.T, np.zeros((2, 2)), atol=2e-12)
    assert np.linalg.norm(expected[1][:2, 2:4]) > .1

    window._marginalize(states[:-3])
    assert window._gaussian_conditionals is saved
    keys = [states[-1], alias, states[-2]]
    before = window.joint_covariance(keys)
    np.testing.assert_allclose(before, independently_reeliminated_covariance(window, keys), atol=2e-12)
    checkpoint = window.snapshot()
    observation = gtsam.PriorFactorVector(states[-1], np.array([.4, -.2]),
                                          gtsam.noiseModel.Diagonal.Sigmas(np.array([.4, .9])))
    window.update([observation], gtsam.Values(), {}, window.time_s, gaussian_only=True)
    assert window._gaussian_conditionals is not saved
    after = window.joint_covariance(keys)
    np.testing.assert_allclose(after, independently_reeliminated_covariance(window, keys), atol=2e-12)
    assert np.linalg.norm(after-before) > .1
    window.restore(checkpoint)
    assert window._gaussian_conditionals is saved
    np.testing.assert_allclose(window.joint_covariance(keys), before, atol=2e-12)


def benchmark_saved_queries(chain_length=48, repeats=30):
    window, states, alias = conditional_chain(chain_length)
    keys = [states[-1], alias, states[-2]]
    actual = window.joint_covariance(keys)
    expected = independently_reeliminated_covariance(window, keys)
    times = {}
    for label, query in [("saved_triangular_solve", window.joint_covariance),
                         ("independent_query_qr", lambda keys: independently_reeliminated_covariance(window, keys))]:
        start = time.perf_counter()
        for _ in range(repeats):
            query(keys)
        times[label] = (time.perf_counter()-start)/repeats
    return dict(chain_length=chain_length, repeats=repeats, query_dimension=len(actual),
                full_dimension=sum(window._conditional_dimensions.values()),
                seconds_per_query=times,
                query_speedup=times["independent_query_qr"]/times["saved_triangular_solve"],
                maximum_absolute_covariance_difference=float(np.max(np.abs(actual-expected))),
                scope="Gaussian covariance query only; excludes model optimization and does not bound model count")


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-repeats", type=int, default=0)
    parser.add_argument("--chain-length", type=int, default=48)
    args = parser.parse_args()
    test_shared_anchor_conditionals_match_independent_history_qr()
    test_qr_rotation_mean_beyond_pi_survives_exact_constraint_and_restore()
    test_saved_qr_queries_keep_units_cross_covariance_and_lifecycle()
    print("PASS: shared-anchor fixed/released Gaussian history matches independent QR")
    if args.benchmark_repeats:
        print(json.dumps(benchmark_saved_queries(args.chain_length, args.benchmark_repeats), indent=2))
