"""Essential mathematical checks for factors in the joint navigation graph."""
import unittest

import gtsam
import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.factors import carrier_factor, carrier_relation_factor, foot_factor, differential_foot_factor


def central_jacobian(factor, values, keys_and_types, epsilon=1e-6):
    columns = []
    for key, kind in keys_and_types:
        original = values.atPose3(key) if kind == "pose" else values.atVector(key)
        dimension = 6 if kind == "pose" else len(original)
        for index in range(dimension):
            delta = np.zeros(dimension)
            delta[index] = epsilon
            plus = gtsam.Values(values)
            minus = gtsam.Values(values)
            if kind == "pose":
                plus.update(key, original.retract(delta))
                minus.update(key, original.retract(-delta))
            else:
                plus_vector, minus_vector = gtsam.Values(), gtsam.Values()
                plus_vector.insert_vector(key, original + delta)
                minus_vector.insert_vector(key, original - delta)
                plus.update(plus_vector)
                minus.update(minus_vector)
            columns.append((factor.whitenedError(plus) - factor.whitenedError(minus)) / (2 * epsilon))
    return np.column_stack(columns)


class JointNavigationFactorsTest(unittest.TestCase):
    def setUp(self):
        self.x0, self.x1 = gtsam.symbol("x", 0), gtsam.symbol("x", 1)
        self.c, self.n = gtsam.symbol("c", 0), gtsam.symbol("n", 0)
        self.values = gtsam.Values()
        self.values.insert(self.x0, gtsam.Pose3(gtsam.Rot3.RzRyRx(.17, -.23, .81), np.array([1., 2., .6])))
        self.values.insert(self.x1, gtsam.Pose3(gtsam.Rot3.RzRyRx(.21, -.19, .87), np.array([1.1, 2.03, .59])))
        self.values.insert(self.c, np.array([1.23, 1.74, .02]))
        self.values.insert(self.n, np.array([2.3, -1.2]))

    def test_carrier_analytic_jacobian_and_full_covariance(self):
        rng = np.random.default_rng(1024)
        B, A = rng.normal(size=(6, 3)), rng.normal(size=(6, 2))
        covariance_root = rng.normal(size=(6, 6))
        Q = covariance_root @ covariance_root.T + .2 * np.eye(6)
        block = EpochBlock(0., rng.normal(size=6), A, B, Q, ("arc_0", "arc_1"))
        baseline = np.array([.01, .35, -.02])
        factor = carrier_factor(self.x1, self.n, block, baseline)
        numeric = central_jacobian(factor, self.values, [(self.x1, "pose"), (self.n, "vector")])
        linear = factor.linearize(self.values)
        np.testing.assert_allclose(linear.getA(), numeric, atol=2e-8, rtol=2e-8)
        residual = B @ self.values.atPose3(self.x1).rotation().rotate(baseline) + A @ self.values.atVector(self.n) - block.y
        self.assertAlmostEqual(2 * factor.error(self.values), residual @ np.linalg.solve(Q, residual), places=11)

    def test_support_analytic_jacobians(self):
        measured, previous = np.array([.2, -.21, -.49]), np.array([.22, -.22, -.5])
        first = foot_factor(self.x0, self.c, previous, .01)
        transition = foot_factor(self.x1, self.c, measured, .01, previous_pose_key=self.x0, previous_measured_body=previous, rho=.83)
        for factor, key_types in [
            (first, [(self.x0, "pose"), (self.c, "vector")]),
            (transition, [(self.x1, "pose"), (self.c, "vector"), (self.x0, "pose")]),
        ]:
            numeric = central_jacobian(factor, self.values, key_types)
            linear = factor.linearize(self.values)
            np.testing.assert_allclose(linear.getA(), numeric, atol=1e-7, rtol=2e-8)

    def test_scalar_carrier_relation_jacobians(self):
        rng = np.random.default_rng(1025)
        keys = [gtsam.symbol("a", i) for i in range(2)]
        for key, value in zip(keys, [2.3, -1.2]):
            self.values.insert_vector(key, np.array([value]))
        B, A = rng.normal(size=(6, 3)), rng.normal(size=(6, 2))
        block = EpochBlock(0., rng.normal(size=6), A, B, np.eye(6), ("arc_0", "arc_1"))
        factor = carrier_relation_factor(self.x1, keys, block, np.array([.01, .35, -.02]))
        numeric = central_jacobian(factor, self.values, [(self.x1, "pose"), *[(key, "vector") for key in keys]])
        linear = factor.linearize(self.values)
        np.testing.assert_allclose(linear.getA(), numeric, atol=2e-8, rtol=2e-8)

    def test_support_arc_whitening_matches_dense_covariance(self):
        sigma, rho, count = .01, .83, 7
        rng = np.random.default_rng(38)
        contact = np.array([.3, -.2, .0])
        values = gtsam.Values()
        values.insert(self.c, contact)
        residuals = rng.normal(0., sigma, size=(count, 3))
        graph = gtsam.NonlinearFactorGraph()
        measurements = []
        for i in range(count):
            key = gtsam.symbol("x", i)
            pose = gtsam.Pose3(gtsam.Rot3.RzRyRx(.05 * i, -.02 * i, .13 * i), np.array([.08 * i, -.03 * i, .5]))
            values.insert(key, pose)
            measured = pose.transformTo(contact) - residuals[i]
            measurements.append(measured)
            options = {} if i == 0 else dict(previous_pose_key=gtsam.symbol("x", i-1), previous_measured_body=measurements[i-1], rho=rho)
            graph.add(foot_factor(key, self.c, measured, sigma, **options))
        indices = np.arange(count)
        temporal_cov = sigma**2 * rho ** np.abs(indices[:, None] - indices[None, :])
        dense_cov = np.kron(temporal_cov, np.eye(3))
        residual = residuals.ravel()
        dense_cost = .5 * residual @ np.linalg.solve(dense_cov, residual)
        self.assertAlmostEqual(graph.error(values), dense_cost, places=10)

    def test_differential_support_analytic_jacobians(self):
        measured, previous = np.array([.2, -.21, -.49]), np.array([.22, -.22, -.5])
        first = differential_foot_factor(self.x0, self.c, previous, .01)
        transition = differential_foot_factor(self.x1, self.c, measured, .01, previous_pose_key=self.x0, previous_measured_body=previous, rho=.83)
        for factor, key_types in [
            (first, [(self.x0, "pose"), (self.c, "vector")]),
            (transition, [(self.x1, "pose"), (self.c, "vector"), (self.x0, "pose")]),
        ]:
            numeric = central_jacobian(factor, self.values, key_types)
            linear = factor.linearize(self.values)
            np.testing.assert_allclose(linear.getA(), numeric, atol=2e-7, rtol=2e-8)


if __name__ == "__main__":
    unittest.main()
