"""Essential mathematical checks for factors in the joint navigation graph."""
import unittest

import gtsam
import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.factors import carrier_factor, carrier_relation_factor, foot_factor, differential_foot_factor
from legsa_gins.paper_rebuild.joint_navigation.factors import (
    ar1_error_factor, foot_error_coordinate_factor, point3_coordinate_factor,
    relative_geometry_coordinate_factor, projected_foot_factor, gnss_position_velocity_factor,
)


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

    def test_latent_foot_error_matches_original_correlated_likelihood(self):
        sigma, rho = .01, .83
        measured0, measured1 = np.array([.22, -.22, -.5]), np.array([.2, -.21, -.49])
        n0, n1 = gtsam.symbol("e", 0), gtsam.symbol("e", 1)
        contact = self.values.atPoint3(self.c)
        for key, pose_key, measured in [(n0, self.x0, measured0), (n1, self.x1, measured1)]:
            self.values.insert_vector(key, self.values.atPose3(pose_key).transformTo(contact)-measured)
        original = gtsam.NonlinearFactorGraph()
        original.add(foot_factor(self.x0, self.c, measured0, sigma))
        original.add(foot_factor(self.x1, self.c, measured1, sigma,
                                 previous_pose_key=self.x0, previous_measured_body=measured0, rho=rho))
        augmented = gtsam.NonlinearFactorGraph()
        augmented.add(gtsam.PriorFactorPoint3(n0, np.zeros(3), gtsam.noiseModel.Isotropic.Sigma(3, sigma)))
        augmented.add(ar1_error_factor(n0, n1, rho, sigma))
        augmented.add(foot_error_coordinate_factor(n0, self.x0, self.c, measured0))
        augmented.add(foot_error_coordinate_factor(n1, self.x1, self.c, measured1))
        self.assertAlmostEqual(augmented.error(self.values), original.error(self.values), places=10)

    def test_exact_coordinate_and_projected_jacobians(self):
        rng = np.random.default_rng(41)
        geometry_keys = [None, gtsam.symbol("d", 1), gtsam.symbol("d", 2), gtsam.symbol("d", 2)]
        noise_keys = [gtsam.symbol("e", i) for i in range(4)]
        for key in dict.fromkeys([*geometry_keys[1:], *noise_keys]):
            self.values.insert_vector(key, rng.normal(size=3))
        measured = rng.normal(size=(4, 3))
        factors = [
            ar1_error_factor(noise_keys[0], noise_keys[1], .83, .01),
            foot_error_coordinate_factor(noise_keys[0], self.x0, self.c, measured[0]),
            relative_geometry_coordinate_factor(geometry_keys[1], self.c, geometry_keys[2]),
            point3_coordinate_factor(geometry_keys[1], {geometry_keys[2]: 1., self.c: 1.}),
            projected_foot_factor(self.x1, geometry_keys, noise_keys, measured),
        ]
        for factor in factors:
            key_types = [(key, "pose" if key in (self.x0, self.x1) else "vector") for key in factor.keys()]
            numeric = central_jacobian(factor, self.values, key_types)
            linear = factor.linearize(self.values)
            np.testing.assert_allclose(linear.getA(), numeric, atol=2e-7, rtol=2e-8)
        np.testing.assert_array_equal(factors[-1].noiseModel().sigmas(), np.zeros(9))

    def test_projected_noise_keeps_sigma_and_removes_common_translation(self):
        from scipy.linalg import helmert
        sigma, count = .01, 4
        rng = np.random.default_rng(42)
        geometry_keys = [None, *[gtsam.symbol("d", i) for i in range(1, count)]]
        noise_keys = [gtsam.symbol("e", i) for i in range(count)]
        geometry = np.vstack([np.zeros(3), rng.normal(size=(count-1, 3))])
        for key, value in zip(geometry_keys[1:], geometry[1:]):
            self.values.insert_vector(key, value)
        H = helmert(count)
        errors = rng.normal(0., sigma, size=(count, 3))
        minimum_noise = H.T @ H @ errors
        for key, value in zip(noise_keys, minimum_noise):
            self.values.insert_vector(key, value)
        rotation = self.values.atPose3(self.x1).rotation()
        measured = np.array([rotation.unrotate(value) for value in geometry])-errors
        factor = projected_foot_factor(self.x1, geometry_keys, noise_keys, measured)
        translated = projected_foot_factor(self.x1, geometry_keys, noise_keys, measured+np.array([.18, -.1, .03]))
        np.testing.assert_allclose(factor.unwhitenedError(self.values), 0., atol=1e-14)
        np.testing.assert_allclose(translated.unwhitenedError(self.values), 0., atol=1e-14)
        latent_cost = sum(.5 * (value @ value) / sigma**2 for value in minimum_noise)
        self.assertAlmostEqual(latent_cost, .5 * np.sum((H @ errors)**2) / sigma**2, places=12)

    def test_changing_subsets_preserve_dense_temporal_noise_likelihood(self):
        # Different Helmert bases are correlated through original arc errors.
        # An IID factor for each visible subset would fail this dense comparison.
        from scipy.linalg import helmert, block_diag
        sigma, rho = .01, .72
        subsets = [(0, 1), (1, 2, 3), (0, 1, 2, 3), (0, 2)]
        rng = np.random.default_rng(45)
        geometry = np.vstack([np.zeros(3), rng.normal(size=(3, 3))])
        values, graph = gtsam.Values(), gtsam.NonlinearFactorGraph()
        pose_key = gtsam.symbol("x", 10)
        values.insert(pose_key, gtsam.Pose3())
        graph.add(gtsam.PriorFactorPose3(pose_key, gtsam.Pose3(), gtsam.noiseModel.Constrained.All(6)))
        geometry_keys = [None, *[gtsam.symbol("d", i) for i in range(1, 4)]]
        for key, point in zip(geometry_keys[1:], geometry[1:]):
            values.insert_point3(key, point)
            graph.add(gtsam.PriorFactorPoint3(key, point, gtsam.noiseModel.Constrained.All(3)))
        projection_blocks, residuals = [], []
        for time, subset in enumerate(subsets):
            for foot in range(4):
                key = gtsam.symbol("e", 4*time+foot)
                values.insert_point3(key, np.zeros(3))
                if time:
                    graph.add(ar1_error_factor(gtsam.symbol("e", 4*(time-1)+foot), key, rho, sigma))
                else:
                    graph.add(gtsam.PriorFactorPoint3(key, np.zeros(3), gtsam.noiseModel.Isotropic.Sigma(3, sigma)))
            observed_errors = rng.normal(0., sigma, (len(subset), 3))
            graph.add(projected_foot_factor(
                pose_key, [geometry_keys[i] for i in subset],
                [gtsam.symbol("e", 4*time+i) for i in subset],
                geometry[list(subset)]-observed_errors))
            select = np.eye(4)[list(subset)]
            H = helmert(len(subset))
            projection_blocks.append(np.kron(H@select, np.eye(3)))
            residuals.append((H@observed_errors).ravel())
        transform = block_diag(*projection_blocks)
        t = np.arange(len(subsets))
        raw_covariance = sigma**2*np.kron(rho**np.abs(t[:, None]-t), np.eye(12))
        covariance = transform@raw_covariance@transform.T
        residual = np.concatenate(residuals)
        dense_cost = .5*residual@np.linalg.solve(covariance, residual)
        linear = graph.linearize(values)
        self.assertAlmostEqual(linear.error(linear.optimize()), dense_cost, places=8)

    @staticmethod
    def _stationary_event(index, subset):
        time = index*.1
        feet = [dict(arc_id=f"arc{i}", foot_id=i, force=100.,
                     point_body=np.array([.2 if i < 2 else -.2, .15 if i % 2 else -.15, -.5]))
                for i in subset]
        return dict(time_s=time, feet=feet,
                    imu=np.array([[.1, 0., 0., -9.81, 0., 0., 0.]]) if index else np.empty((0, 7)),
                    gnss_position=np.array([0., 0., .5]), gnss_velocity=np.zeros(3),
                    carrier=EpochBlock(time, np.array([0., -.35, 0.]), np.empty((3, 0)),
                                       np.eye(3), np.eye(3)*.0001, ()))

    def test_branch_subset_bridge_prediction_and_marginalization(self):
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        branch = NavigationBranch(dict(baseline_body=[0., -.35, 0.], lag_s=.25))
        group = [dict(group_id="group", arc_ids=tuple(f"arc{i}" for i in range(4)),
                      mode="common_translation_release")]
        # The first two subsets have no shared foot: no bridge until event 2.
        subsets = [(0, 1), (2, 3), (1, 2), (0, 2, 3), (0, 1, 2, 3), (0, 1), (1, 2, 3)]
        for index, subset in enumerate(subsets):
            event = self._stationary_event(index, subset)
            if index:
                before = branch.snapshot()
                prediction = branch.predict_external(event)
                self.assertEqual(prediction["measurement_time_s"], event["time_s"])
                self.assertEqual(prediction["prior_time_s"], branch.time)
                self.assertEqual(branch.time, before.window.time_s)
                self.assertEqual(tuple(branch.window.values.keys()), tuple(before.window.values.keys()))
                self.assertEqual(len(prediction["row_ids"]), 9)
                self.assertTrue(np.all(np.linalg.eigvalsh(prediction["covariance"]) > 0.))
                self.assertGreater(np.linalg.norm(prediction["covariance"][:3, 3:6]), 0.)
            branch.step(event, index, support_models=group)
            self.assertEqual(branch.last_factor_counts["differential"], len(subset)-1)
            np.testing.assert_allclose(branch.current_output()["p"], [0., 0., .5], atol=1e-10)
            if index == 1:
                self.assertEqual(len({value[0] for value in branch.support_geometry["group"].values()}), 2)
        self.assertEqual(len({value[0] for value in branch.support_geometry["group"].values()}), 1)
        self.assertGreater(branch.window.marginalized_total, 0)
        self.assertEqual(set(branch.foot_noise_history), {f"arc{i}" for i in range(4)})
        # State and factor closures remain reproducible from an actual snapshot.
        restored = NavigationBranch(branch.metadata)
        restored.restore(branch.snapshot())
        event = self._stationary_event(len(subsets), (0, 1, 2, 3))
        np.testing.assert_allclose(restored.predict_external(event)["covariance"],
                                   branch.predict_external(event)["covariance"], atol=1e-12)

    def test_release_preserves_unaffected_foot_and_does_not_reset_error(self):
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        branch = NavigationBranch(dict(baseline_body=[0., -.35, 0.], lag_s=.25))
        branch.step(self._stationary_event(0, range(4)), 0)
        group = [dict(group_id="three", arc_ids=("arc0", "arc1", "arc2"),
                      mode="common_translation_release")]
        branch.step(self._stationary_event(1, (0, 1, 3)), 1, support_models=group)
        self.assertEqual(branch.last_factor_counts["foot"], 1)
        self.assertEqual(branch.last_factor_counts["differential"], 1)
        self.assertEqual(set(branch.foot_noise_history), {"arc0", "arc1"})
        old_key = branch.foot_noise_history["arc0"][0]
        # A singleton supplies no direction and must not restart an IID history.
        branch.step(self._stationary_event(2, (0, 3)), 2, support_models=group)
        self.assertEqual(branch.foot_noise_history["arc0"][0], old_key)
        branch.step(self._stationary_event(3, (0, 1, 2, 3)), 3, support_models=group)
        self.assertEqual(branch.last_factor_counts["foot"], 1)
        self.assertEqual(branch.last_factor_counts["differential"], 2)
        group[0]["mode"] = "relative_release"
        branch.step(self._stationary_event(4, range(4)), 4, support_models=group)
        self.assertEqual(branch.last_factor_counts["foot"], 1)
        self.assertEqual(branch.last_factor_counts["differential"], 0)
        self.assertTrue(np.all(np.linalg.eigvalsh(branch.predict_external(
            self._stationary_event(5, range(4)))["covariance"]) > 0.))

    def test_joint_gnss_prediction_noise_matches_consumed_factor(self):
        velocity_key = gtsam.symbol("v", 1)
        self.values.insert_vector(velocity_key, np.array([.2, .1, -.01]))
        covariance = np.eye(6)*.01
        covariance[:3, 3:] = covariance[3:, :3] = np.eye(3)*.003
        factor = gnss_position_velocity_factor(self.x1, velocity_key, [1., 2., .5], [0., 0., 0.], covariance)
        numeric = central_jacobian(factor, self.values, [(self.x1, "pose"), (velocity_key, "vector")])
        np.testing.assert_allclose(factor.linearize(self.values).getA(), numeric, atol=2e-8, rtol=2e-8)

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
