"""One linear conditional/reconstruction check, including an exact coordinate."""

import gtsam
import numpy as np
from unittest.mock import patch

from legsa_gins.paper_rebuild.joint_navigation.window import JointWindow, key_ordering


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


if __name__ == "__main__":
    test_shared_anchor_conditionals_match_independent_history_qr()
    test_qr_rotation_mean_beyond_pi_survives_exact_constraint_and_restore()
    print("PASS: shared-anchor fixed/released Gaussian history matches independent QR")
