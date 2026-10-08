"""Essential mathematical checks for factors in the joint navigation graph."""
import unittest

import gtsam
import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.factors import carrier_factor, carrier_relation_factor, foot_factor, differential_foot_factor
from legsa_gins.paper_rebuild.joint_navigation.factors import (
    ar1_error_factor, foot_error_coordinate_factor, point3_coordinate_factor,
    relative_geometry_coordinate_factor, projected_foot_factor, gnss_position_velocity_factor,
    gnss_antenna_factor, gnss_antenna_prediction, gravity_tilt_factor,
    FootErrorExpression, algebraic_foot_error_factor,
)


def central_jacobian(factor, values, keys_and_types, epsilon=1e-6):
    columns = []
    for key, kind in keys_and_types:
        original = (values.atPose3(key) if kind == "pose" else
                    values.atConstantBias(key) if kind == "bias" else values.atVector(key))
        dimension = 6 if kind in ("pose", "bias") else len(original)
        for index in range(dimension):
            delta = np.zeros(dimension)
            delta[index] = epsilon
            plus = gtsam.Values(values)
            minus = gtsam.Values(values)
            if kind == "pose":
                plus.update(key, original.retract(delta))
                minus.update(key, original.retract(-delta))
            elif kind == "bias":
                plus.update(key, gtsam.imuBias.ConstantBias(original.accelerometer()+delta[:3], original.gyroscope()+delta[3:]))
                minus.update(key, gtsam.imuBias.ConstantBias(original.accelerometer()-delta[:3], original.gyroscope()-delta[3:]))
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

    def test_algebraic_foot_error_jacobians_fixed_and_released_history(self):
        common0, common1 = gtsam.symbol("q", 0), gtsam.symbol("q", 1)
        self.values.insert_vector(common0, np.array([.3, -.1, .2]))
        self.values.insert_vector(common1, np.array([.2, -.2, .1]))
        fixed = FootErrorExpression(self.x0, self.c, (.1, -.2, -.5))
        released = FootErrorExpression(self.x1, self.c, (.15, -.18, -.51), common1)
        old_released = FootErrorExpression(self.x0, self.c, (.1, -.2, -.5), common0)
        for previous in (None, fixed, old_released):
            factor = algebraic_foot_error_factor(released, .01, previous=previous, rho=.8)
            kinds = [(key, "pose" if key in (self.x0, self.x1) else "vector") for key in factor.keys()]
            numeric = central_jacobian(factor, self.values, kinds)
            linear = factor.linearize(self.values)
            np.testing.assert_allclose(linear.getA(), numeric, atol=1e-7, rtol=2e-8)

    def test_algebraic_subsets_match_dense_AR_likelihood_without_exact_foot_factors(self):
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
        history, blocks, residuals = {}, [], []
        expressions = []
        for time, subset in enumerate(subsets):
            common = gtsam.symbol("q", time)
            values.insert_vector(common, np.zeros(3))
            errors = rng.normal(0., sigma, (len(subset), 3))
            current_expressions = []
            for foot, error in zip(subset, errors):
                expression = FootErrorExpression(pose_key, geometry_keys[foot], tuple(geometry[foot]-error), common)
                old, correlation = (None, 0.) if foot not in history else (history[foot][0], rho**(time-history[foot][1]))
                graph.add(algebraic_foot_error_factor(expression, sigma, previous=old, rho=correlation))
                history[foot] = expression, time
                current_expressions.append(expression)
            expressions.append(current_expressions)
            H = helmert(len(subset))
            blocks.append(np.kron(H @ np.eye(4)[list(subset)], np.eye(3)))
            residuals.append((H @ errors).ravel())
        transform = block_diag(*blocks)
        times = np.arange(len(subsets))
        covariance = transform @ (sigma**2*np.kron(rho**np.abs(times[:, None]-times), np.eye(12))) @ transform.T
        residual = np.concatenate(residuals)
        expected = .5*residual @ np.linalg.solve(covariance, residual)
        optimized = gtsam.LevenbergMarquardtOptimizer(graph, values).optimize()
        self.assertAlmostEqual(graph.error(optimized), expected, places=8)
        # The original nonlinear projected equality is an identity for arbitrary
        # attitude, geometry and q, not a soft constraint accepted by LM's mu.
        optimized.update(pose_key, gtsam.Pose3(gtsam.Rot3.RzRyRx(.2, -.1, .7), [.5, -.2, .3]))
        for group in expressions:
            H = helmert(len(group))
            raw = np.array([optimized.atPose3(e.pose_key).rotation().unrotate(
                np.zeros(3) if e.point_key is None else optimized.atPoint3(e.point_key))-np.asarray(e.measured_body)
                for e in group])
            errors = np.array([e.evaluate(optimized) for e in group])
            np.testing.assert_allclose(H @ (raw-errors), 0., atol=1e-14)

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
        self.assertEqual(set(branch.foot_error_history), {f"arc{i}" for i in range(4)})
        # State and factor closures remain reproducible from an actual snapshot.
        branch.predictive_score = 17.3
        branch.predictive_row_count = 21
        branch.predictive_frontier = len(subsets)-1
        branch.integer_lineage = (("physical_proposal", ("arc", 2)),)
        restored = NavigationBranch(branch.metadata)
        restored.restore(branch.snapshot())
        for name in ("predictive_score", "predictive_row_count", "predictive_frontier", "integer_lineage"):
            self.assertEqual(getattr(restored, name), getattr(branch, name))
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
        self.assertEqual(set(branch.foot_error_history), {"arc0", "arc1"})
        old_key = branch.foot_error_history["arc0"][0]
        # A singleton supplies no direction and must not restart an IID history.
        branch.step(self._stationary_event(2, (0, 3)), 2, support_models=group)
        self.assertEqual(branch.foot_error_history["arc0"][0], old_key)
        branch.step(self._stationary_event(3, (0, 1, 2, 3)), 3, support_models=group)
        self.assertEqual(branch.last_factor_counts["foot"], 1)
        self.assertEqual(branch.last_factor_counts["differential"], 2)
        group[0]["mode"] = "relative_release"
        branch.step(self._stationary_event(4, range(4)), 4, support_models=group)
        self.assertEqual(branch.last_factor_counts["foot"], 1)
        self.assertEqual(branch.last_factor_counts["differential"], 0)
        self.assertTrue(np.all(np.linalg.eigvalsh(branch.predict_external(
            self._stationary_event(5, range(4)))["covariance"]) > 0.))

    def test_external_prediction_matches_actual_imu_factor_under_rotation(self):
        from gtsam.symbol_shorthand import X, V
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        metadata = dict(baseline_body=[0., -.35, 0.], accel_noise_density=.1,
                        gyro_noise_density=.02, accel_bias_random_walk=.0002,
                        gyro_bias_random_walk=.00002)
        branch = NavigationBranch(metadata, use_foot=False)
        branch.step(self._stationary_event(0, ()), 0)
        event = self._stationary_event(1, ())
        event["time_s"] = 1.
        event["imu"] = np.tile([.01, .1, .2, -9.7, .2, .1, .4], (100, 1))
        prediction = branch.predict_external(event)
        # Independent oracle: really add the source IMU factor, but no current
        # GNSS/carrier/foot observation, then query the propagated joint state.
        propagated = NavigationBranch(metadata, use_foot=False)
        propagated.restore(branch.snapshot())
        propagated.step(dict(event, gnss_position=None, gnss_velocity=None, carrier=None), 1)
        covariance = propagated.joint_covariance([X(1), V(1)])
        rotation = propagated.pose.rotation().matrix()
        baseline = np.asarray(metadata["baseline_body"])
        x, y, z = baseline
        skew = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
        H = np.zeros((9, 9))
        H[:3, 3:6] = rotation
        H[3:6, 6:9] = np.eye(3)
        H[6:, :3] = -rotation@skew
        sensor = np.diag([.05**2]*3+[.03**2]*3+[.0001]*3)
        expected = H@covariance@H.T+sensor
        np.testing.assert_allclose(prediction["covariance"], expected, atol=2e-8, rtol=2e-8)
        legacy_r, legacy_s = branch.predict_gnss_position(event)
        np.testing.assert_allclose(legacy_r, prediction["innovation"][:3], atol=1e-12)
        np.testing.assert_allclose(legacy_s, expected[:3, :3], atol=2e-8, rtol=2e-8)

    def test_external_prediction_uses_only_common_physically_predictable_rows(self):
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        metadata = dict(baseline_body=[0., -.35, 0.])
        branch = NavigationBranch(metadata, use_foot=False)
        branch.step(self._stationary_event(0, ()), 0)
        event = self._stationary_event(1, ())
        B = np.vstack([np.eye(3), np.eye(3)])
        A = np.r_[np.zeros(3), np.ones(3)].reshape(6, 1)
        root = np.array([[.01, 0.], [.003, .007]])
        block_covariance = np.kron(root@root.T, np.eye(3))
        event["carrier"] = EpochBlock(.1, B@np.array(metadata["baseline_body"]), A, B,
                                       block_covariance, ("new_physical_arc",))
        before = branch.snapshot()
        prediction = branch.predict_external(event)
        self.assertEqual(prediction["excluded_unknown_ambiguity_rows"], [3, 4, 5])
        self.assertEqual(len(prediction["row_ids"]), 9)
        self.assertFalse(branch.ambiguity_keys)
        self.assertEqual(tuple(branch.window.values.keys()), tuple(before.window.values.keys()))
        self.assertEqual(branch.window.error(), sum(f.error(before.window.values)
                         for f in before.window.factors)+before.window.objective_offset)
        # Marginalizing unavailable rows takes Q[known,known], not the smaller
        # conditional covariance obtained by pretending the omitted rows are known.
        code_event = dict(event, carrier=EpochBlock(.1, event["carrier"].y[:3],
                          np.empty((3, 0)), B[:3], block_covariance[:3, :3], ()))
        code_prediction = branch.predict_external(code_event)
        self.assertEqual(prediction["row_ids"], code_prediction["row_ids"])
        np.testing.assert_allclose(prediction["covariance"], code_prediction["covariance"], atol=1e-12)

    def test_antenna_factor_pose_velocity_bias_jacobians(self):
        velocity_key, bias_key = gtsam.symbol("v", 1), gtsam.symbol("b", 1)
        self.values.insert_vector(velocity_key, np.array([.3, .1, -.02]))
        self.values.insert(bias_key, gtsam.imuBias.ConstantBias([.01, -.02, .03], [.001, -.002, .003]))
        covariance = np.eye(6)*.01
        covariance[:3, 3:] = covariance[3:, :3] = np.eye(3)*.002
        options = ([.03, .03, -.30], [.04, -.02, -.26], [.4, -.2, .1])
        factor = gnss_antenna_factor(self.x1, velocity_key, bias_key, [1., 2., .5], [.2, .1, 0.], covariance, *options)
        numeric = central_jacobian(factor, self.values,
                                   [(self.x1, "pose"), (velocity_key, "vector"), (bias_key, "bias")])
        linear = factor.linearize(self.values)
        np.testing.assert_allclose(linear.getA(), numeric, atol=2e-8, rtol=2e-8)
        for p, v, C in (([1., 2., .5], None, covariance[:3, :3]),
                        (None, [.2, .1, 0.], covariance[3:, 3:])):
            part = gnss_antenna_factor(self.x1, velocity_key, bias_key, p, v, C, *options)
            types = [(key, "pose" if key == self.x1 else "bias" if key == bias_key else "vector")
                     for key in part.keys()]
            linear = part.linearize(self.values)
            np.testing.assert_allclose(linear.getA(), central_jacobian(part, self.values, types), atol=2e-8, rtol=2e-8)

    def test_event_antenna_prediction_and_consumption_share_covariance(self):
        from gtsam.symbol_shorthand import X, V, B
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        metadata = dict(baseline_body=[0., -.35, 0.], accel_noise_density=.01,
                        gyro_noise_density=.002, accel_bias_random_walk=.0002,
                        gyro_bias_random_walk=.0002)
        branch = NavigationBranch(metadata, use_foot=False)
        branch.step(self._stationary_event(0, ()), 0)
        event = self._stationary_event(1, ())
        event["imu"] = np.tile([.01, .1, .2, -9.7, .2, .1, .4], (10, 1))
        event.update(gnss_position_leverarm_body_m=np.array([.03, .03, -.3]),
                     gnss_velocity_leverarm_body_m=np.array([.04, -.02, -.26]),
                     gnss_angular_rate_body_rad_s=np.array([.21, .11, .39]),
                     gnss_angular_rate_source_time_s=.098,
                     last_gyro_source_noise_interval_s=.003,
                     gnss_position_covariance=np.diag([.04, .03, .02])**2,
                     gnss_velocity_covariance=np.array([[.004, .0002, 0.], [.0002, .002, 0.], [0., 0., .003]]))
        prediction = branch.predict_external(event)
        propagated = NavigationBranch(metadata, use_foot=False)
        propagated.restore(branch.snapshot())
        propagated.step(dict(event, gnss_position=None, gnss_velocity=None, carrier=None), 1)
        P = propagated.joint_covariance([X(1), V(1), B(1)])
        pose, rotation = propagated.pose, propagated.pose.rotation().matrix()
        p_lever, v_lever = event["gnss_position_leverarm_body_m"], event["gnss_velocity_leverarm_body_m"]
        omega = event["gnss_angular_rate_body_rad_s"]
        relative = np.cross(omega-propagated.bias.gyroscope(), v_lever)
        skew = branch._skew
        H = np.zeros((9, 15))
        H[:3, :3], H[:3, 3:6] = -rotation@skew(p_lever), rotation
        H[3:6, :3], H[3:6, 6:9], H[3:6, 12:15] = -rotation@skew(relative), np.eye(3), rotation@skew(v_lever)
        H[6:, :3] = -rotation@skew(np.asarray(metadata["baseline_body"]))
        physical = branch._gnss_inputs(event, pose)
        noise = np.zeros((9, 9));noise[:6, :6] = physical["covariance"];noise[6:, 6:] = np.eye(3)*.0001
        np.testing.assert_allclose(prediction["covariance"], H@P@H.T+noise, atol=2e-8, rtol=2e-8)
        expected_p, expected_v = gnss_antenna_prediction(pose, propagated.velocity, propagated.bias.gyroscope(), p_lever, v_lever, omega)
        np.testing.assert_allclose(prediction["predicted"][:6], np.r_[expected_p, expected_v], atol=1e-10)
        gyro_map = -rotation@skew(v_lever)
        extra = gyro_map@(np.eye(3)*metadata["gyro_noise_density"]**2/.003)@gyro_map.T
        np.testing.assert_allclose(physical["covariance"][3:, 3:], event["gnss_velocity_covariance"]+extra, atol=1e-12)
        self.assertGreater(np.trace(extra), 0.)
        self.assertIn("cross_unmodelled", prediction["source_covariance_assumption"])
        # Actually consume the event; the custom factor receives the identical
        # covariance at the same predicted pose, not a pre-corrected p/v product.
        branch.step(event, 1)
        antenna = next(f for f in branch.window.factors if tuple(f.keys()) == (X(1), V(1), B(1)))
        np.testing.assert_allclose(antenna.noiseModel().covariance(), physical["covariance"], atol=1e-12)

    def test_provider_eligibility_is_not_rethresholded(self):
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        branch = NavigationBranch(dict(baseline_body=[0., -.35, 0.]))
        event = self._stationary_event(0, (0, 1))
        event["feet"][0].update(support_eligible=True, force=1.)
        event["feet"][1].update(support_eligible=False, force=1000.)
        branch.step(event, 0)
        self.assertEqual(branch.last_factor_counts["foot"], 1)
        self.assertEqual(set(branch.contact_keys), {"arc0"})

    def test_gravity_tilt_has_no_world_yaw_or_translation_information(self):
        rotation = self.values.atPose3(self.x1).rotation()
        gravity = np.array([0., 0., 1.])
        body = rotation.unrotate(gravity)
        factor = gravity_tilt_factor(self.x1, body, gravity, .05)
        linear = factor.linearize(self.values)
        columns = []
        for index in range(6):
            delta = np.zeros(6); delta[index] = 1e-6
            plus, minus = gtsam.Values(self.values), gtsam.Values(self.values)
            pose = self.values.atPose3(self.x1)
            plus.update(self.x1, pose.retract(delta)); minus.update(self.x1, pose.retract(-delta))
            columns.append((-factor.linearize(plus).getb()+factor.linearize(minus).getb())/2e-6)
        numeric = np.column_stack(columns)
        np.testing.assert_allclose(linear.getA(), numeric, atol=2e-8, rtol=2e-8)
        self.assertEqual(np.linalg.matrix_rank(linear.getA()), 2)
        np.testing.assert_allclose(linear.getA()[:, :3] @ body, 0., atol=1e-12)
        np.testing.assert_array_equal(linear.getA()[:, 3:], np.zeros((2, 3)))
        for yaw in (-2.4, -.3, 1.8):
            values = gtsam.Values(self.values)
            values.update(self.x1, gtsam.Pose3(gtsam.Rot3.Rz(yaw).compose(rotation), [9., 3., 4.]))
            self.assertLess(factor.error(values), 1e-20)

    def test_gravity_tilt_log_uses_angle_and_its_off_solution_jacobian(self):
        factor = gravity_tilt_factor(self.x1, [0., 0., 1.], [0., 0., 1.], .05)
        numeric = central_jacobian(factor, self.values, [(self.x1, "pose")])
        linear = factor.linearize(self.values)
        np.testing.assert_allclose(linear.getA(), numeric, atol=2e-8, rtol=2e-8)
        values = gtsam.Values(self.values)
        values.update(self.x1, gtsam.Pose3(gtsam.Rot3.Rx(2.8), [0., 0., 0.]))
        self.assertAlmostEqual(factor.error(values), .5*(2.8/.05)**2, places=8)
        values.update(self.x1, gtsam.Pose3(gtsam.Rot3.Rx(np.pi), [0., 0., 0.]))
        with self.assertRaisesRegex(ValueError, "antipodal"):
            factor.error(values)

    def test_asynchronous_bootstrap_uses_original_nodes_before_one_optimization(self):
        from gtsam.symbol_shorthand import X
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        events = [self._stationary_event(i, ()) for i in range(4)]
        events[0].update(carrier=None, gnss_velocity=None)
        events[1].update(carrier=None, gnss_position=None)
        branch = NavigationBranch(dict(baseline_body=[0., -.35, 0.], lag_s=.05), use_foot=False)
        report = branch.bootstrap(events, gtsam.Rot3.Ypr(.4, 0., 0.),
                                  gravity_tilt=dict(direction_body=[0., 0., 1.], sigma_rad=.05))
        self.assertEqual(report["status"], "NO_INIT")
        self.assertEqual(report["nonlinear_support"], "UNRESOLVED")
        self.assertTrue(report["local_full_rank"])
        self.assertEqual(branch.window.marginalized_total, 0)
        self.assertEqual(sum(isinstance(f, gtsam.ImuFactor) for f in branch.window.factors), 3)
        self.assertFalse(any(isinstance(f, gtsam.PriorFactorPose3) for f in branch.window.factors))
        for i, event in enumerate(events):
            self.assertEqual(branch.window.times[X(i)], event["time_s"])
        self.assertTrue(any(isinstance(f, gtsam.GPSFactor) and f.keys()[0] == X(0)
                            for f in branch.window.factors))
        np.testing.assert_allclose(branch.pose.rotation().rpy(), 0., atol=1e-8)
        snapshot = branch.snapshot()
        restored = NavigationBranch(branch.metadata, use_foot=False); restored.restore(snapshot)
        self.assertEqual(restored.bootstrap_diagnostics, branch.bootstrap_diagnostics)
        branch.accept_bootstrap(dict(qualified=True, method="controlled_test_known_direction"))
        self.assertGreater(branch.window.marginalized_total, 0)
        self.assertEqual(branch.bootstrap_status, "INITIALIZED")

    def test_bootstrap_iteration_budget_is_distinct_from_direction_exclusion(self):
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        branch = NavigationBranch(dict(baseline_body=[0., -.35, 0.], bootstrap_max_iterations=1), use_foot=False)
        events = [self._stationary_event(i, ()) for i in range(4)]
        report = branch.bootstrap(events, gtsam.Rot3.Ypr(1.8, 0., 0.),
                                  gravity_tilt=dict(direction_body=[0., 0., 1.], sigma_rad=.05))
        self.assertTrue(report["local_full_rank"])
        self.assertTrue(report["solver_budget_exhausted"])
        self.assertFalse(report["solver_converged"])
        self.assertEqual(report["solver_status"], "ITERATION_BUDGET_EXHAUSTED")
        self.assertEqual(report["status"], "NO_INIT")
        self.assertEqual(report["nonlinear_support"], "UNRESOLVED")

    def test_bootstrap_without_direction_stays_rank_deficient_and_unmarginalized(self):
        from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
        events = [dict(self._stationary_event(i, ()), carrier=None) for i in range(4)]
        branch = NavigationBranch(dict(baseline_body=[0., -.35, 0.], lag_s=.05), use_foot=False)
        report = branch.bootstrap(events, gtsam.Rot3.Ypr(.8, 0., 0.),
                                  gravity_tilt=dict(direction_body=[0., 0., 1.], sigma_rad=.05))
        self.assertFalse(report["local_full_rank"])
        self.assertEqual(report["state_dimension"]-report["numerical_rank"], 1)
        self.assertEqual(branch.bootstrap_status, "NO_INIT")
        self.assertEqual(branch.window.marginalized_total, 0)
        np.testing.assert_allclose(branch.pose.rotation().rpy(), [0., 0., .8], atol=1e-12)

    def test_initial_released_group_predicts_after_lag_marginalization(self):
        from gtsam.symbol_shorthand import X, V
        from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator
        from legsa_gins.paper_rebuild.joint_navigation.synthetic import generate_scene
        scene = generate_scene(duration_s=90., seed=6100801)
        # First observed support pair, chosen from input topology, not fault truth.
        arcs = tuple(sorted(foot["arc_id"] for foot in scene["events"][0]["feet"]))
        model = dict(group_id="initial_pair", arc_ids=arcs, mode="common_translation_release")
        navigator = JointNavigator(scene["metadata"], "U3", monitor_support=False, support_models=[model])
        compared = False
        for index, event in enumerate(scene["events"]):
            if event["time_s"] > 5.6 + 1e-9:
                break
            navigator.events.append((index, event))
            if abs(event["time_s"] - 5.4) < 1e-9:
                branch = navigator.branches[0]
                self.assertGreater(branch.window.marginalized_total, 0)
                self.assertTrue(branch.integer_lineage)
                keys = [X(branch.index), V(branch.index), branch.bias_key,
                        *branch.ambiguity_keys.values()]
                sparse = branch.joint_covariance(keys)
                linear = branch.window.graph.linearize(branch.window.values)
                other = [key for key in branch.window.values.keys() if key not in keys]
                # Independent dense constrained QR oracle at the formerly
                # failing state; production uses sparse local QR throughout.
                dense = gtsam.JacobianFactor(linear, branch._ordering([*other, *keys]))
                _, remainder = dense.eliminate(branch._ordering(other))
                final = gtsam.GaussianFactorGraph(); final.push_back(remainder)
                dense = gtsam.JacobianFactor(final, branch._ordering(keys))
                conditional, _ = dense.eliminate(branch._ordering(keys))
                root = np.linalg.solve(conditional.R(), np.diag(conditional.get_model().sigmas()))
                np.testing.assert_allclose(sparse, root @ root.T, atol=1e-10, rtol=1e-6)
                self.assertGreater(np.linalg.eigvalsh(sparse)[0], 0.)
                compared = True
            navigator._advance(navigator._filter(event), index)
        self.assertTrue(compared)
        self.assertGreater(navigator.branches[0].predictive_frontier, 81)

    def test_joint_gnss_prediction_noise_matches_consumed_factor(self):
        velocity_key = gtsam.symbol("v", 1)
        self.values.insert_vector(velocity_key, np.array([.2, .1, -.01]))
        covariance = np.eye(6)*.01
        covariance[:3, 3:] = covariance[3:, :3] = np.eye(3)*.003
        factor = gnss_position_velocity_factor(self.x1, velocity_key, [1., 2., .5], [0., 0., 0.], covariance)
        numeric = central_jacobian(factor, self.values, [(self.x1, "pose"), (velocity_key, "vector")])
        linear = factor.linearize(self.values)
        np.testing.assert_allclose(linear.getA(), numeric, atol=2e-8, rtol=2e-8)

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
