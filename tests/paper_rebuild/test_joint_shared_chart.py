"""Shared-chart branch checks for support models, startup and conditioning."""
import unittest
from unittest.mock import patch

import gtsam
import numpy as np
from gtsam.symbol_shorthand import B, V, X

from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.branch import NavigationBranch
from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator


def stationary_event(index, subset):
    time = index * .1
    feet = [dict(arc_id=f"arc{i}", foot_id=i, force=100.,
                 point_body=np.array([.2 if i < 2 else -.2, .15 if i % 2 else -.15, -.5]))
            for i in subset]
    return dict(
        time_s=time, feet=feet,
        imu=np.array([[.1, 0., 0., -9.81, 0., 0., 0.]]) if index else np.empty((0, 7)),
        gnss_position=np.array([0., 0., .5]), gnss_velocity=np.zeros(3),
        carrier=EpochBlock(time, np.array([0., -.35, 0.]), np.empty((3, 0)),
                           np.eye(3), np.eye(3) * .0001, ()))


class JointSharedChartTest(unittest.TestCase):
    def setUp(self):
        self.metadata = dict(baseline_body=[0., -.35, 0.], lag_s=.25)

    def test_three_models_subset_bridge_marginalization_and_snapshot(self):
        background = NavigationBranch(self.metadata)
        navigator = JointNavigator(self.metadata, mode="U1")
        shadows = {mode: NavigationBranch(self.metadata) for mode in
                   ("fixed", "common_translation_release", "relative_release")}
        subsets = [(0, 1), (2, 3), (1, 2), (0, 2, 3), (0, 1, 2, 3), (0, 1), (1, 2, 3)]
        for index, subset in enumerate(subsets):
            event = stationary_event(index, subset)
            if index:
                event["gnss_position"] += np.array([.01 * np.sin(index), .01 * np.cos(index), .003])
            background.step(event, index)
            anchor = background.export_linearization_anchor()
            for mode, shadow in shadows.items():
                models = [dict(group_id="group", arc_ids=tuple(f"arc{k}" for k in range(4)), mode=mode)]
                with self.subTest(index=index, mode=mode), patch.object(
                        gtsam, "LevenbergMarquardtOptimizer",
                        side_effect=AssertionError("Gaussian shadow invoked LM")):
                    shadow.step(event, index, support_models=models, linearization_anchor=anchor)
                    self.assertTrue(shadow.window.gaussian_only)
                    prediction = shadow.predict_external(stationary_event(index + 1, range(4)))
                    self.assertEqual(prediction["prediction_linearization"], "COMMON_ANCHOR_AFFINE_GAUSSIAN")
                    self.assertTrue(np.isfinite(prediction["covariance"]).all())
                    covariance = shadow.joint_covariance([X(index), V(index), B(index)])
                    self.assertTrue(np.isfinite(covariance).all())
                    # Read out the same physical direction by two coordinate
                    # routes: root's shared-anchor pushforward and the branch's
                    # transported conditional-mean covariance.
                    direction = navigator._direction_summary(shadow, index)
                    rotation = shadow.pose.rotation()
                    body_unit = np.asarray(self.metadata["baseline_body"])
                    body_unit = body_unit / np.linalg.norm(body_unit)
                    bx, by, bz = body_unit
                    cross = np.array([[0., -bz, by], [bz, 0., -bx], [-by, bx, 0.]])
                    local_jacobian = -rotation.matrix() @ cross
                    basis = np.asarray(direction["baseline_tangent_basis_n"])
                    expected = basis.T @ local_jacobian @ covariance[:3, :3] @ local_jacobian.T @ basis
                    np.testing.assert_allclose(direction["baseline_tangent_covariance_rad2"],
                                               expected, atol=1e-12, rtol=1e-6)
                    yaw_gradient = np.empty(3)
                    for axis in range(3):
                        delta = np.eye(3)[axis] * 1e-6
                        difference = rotation.retract(delta).yaw() - rotation.retract(-delta).yaw()
                        yaw_gradient[axis] = np.arctan2(np.sin(difference), np.cos(difference)) / 2e-6
                    expected_yaw_variance = yaw_gradient @ covariance[:3, :3] @ yaw_gradient
                    np.testing.assert_allclose(direction["yaw_conditional_std_rad"] ** 2,
                                               expected_yaw_variance, atol=1e-12, rtol=1e-6)
                    restored = NavigationBranch(self.metadata)
                    restored.restore(shadow.snapshot())
                    repeated = restored.predict_external(stationary_event(index + 1, range(4)))
                    np.testing.assert_allclose(prediction["predicted"], repeated["predicted"], atol=1e-12)
                    np.testing.assert_allclose(prediction["covariance"], repeated["covariance"], atol=1e-12)

    def test_contacts_map_by_physical_arc_instead_of_local_key(self):
        background = NavigationBranch(self.metadata)
        background.step(stationary_event(0, range(4)), 0)
        shadow = NavigationBranch(self.metadata)
        models = [dict(group_id="partial", arc_ids=("arc0", "arc1"), mode="common_translation_release")]
        with patch.object(gtsam, "LevenbergMarquardtOptimizer", side_effect=AssertionError("Gaussian shadow invoked LM")):
            shadow.step(stationary_event(0, range(4)), 0, support_models=models,
                        linearization_anchor=background.export_linearization_anchor())
        # c0 belongs to a different physical foot after a partial release.
        self.assertNotEqual(shadow.contact_keys["arc2"], background.contact_keys["arc2"])
        np.testing.assert_array_equal(
            shadow.window.linearization_values.atPoint3(shadow.contact_keys["arc2"]),
            background.window.values.atPoint3(background.contact_keys["arc2"]))

    def test_async_bootstrap_uses_one_complete_background_chart_without_lm(self):
        events = [stationary_event(index, ()) for index in range(4)]
        events[0].update(carrier=None, gnss_velocity=None)
        events[1].update(carrier=None, gnss_position=None)
        seed = gtsam.Rot3.Ypr(.4, 0., 0.)
        tilt = dict(direction_body=[0., 0., 1.], sigma_rad=.05)
        background = NavigationBranch(self.metadata, use_foot=False)
        background.bootstrap(events, seed, gravity_tilt=tilt)
        full_anchor = background.export_linearization_anchor()
        shadow = NavigationBranch(self.metadata, use_foot=False)
        with patch.object(gtsam, "LevenbergMarquardtOptimizer", side_effect=AssertionError("Gaussian bootstrap invoked LM")):
            report = shadow.bootstrap(events, seed, gravity_tilt=tilt, linearization_anchor=full_anchor)
            self.assertEqual(report["qualification_scope"], "COMMON_LINEARIZATION_ONLY")
            shadow.accept_bootstrap(dict(qualified=True, scope="COMMON_LINEARIZATION_ONLY", globally_certified=False))

    def test_integer_condition_preserves_gaussian_solve(self):
        event = stationary_event(0, ())
        code = event["carrier"].y
        event["carrier"] = EpochBlock(
            0., np.r_[code, code + .19 * np.array([2, -1, 4])],
            np.r_[np.zeros((3, 3)), .19 * np.eye(3)], np.r_[np.eye(3), np.eye(3)],
            np.diag([.01 ** 2] * 3 + [.002 ** 2] * 3), ("n0", "n1", "n2"))
        background = NavigationBranch(self.metadata, use_foot=False)
        background.step(event, 0)
        shadow = NavigationBranch(self.metadata, use_foot=False)
        with patch.object(gtsam, "LevenbergMarquardtOptimizer", side_effect=AssertionError("Gaussian condition invoked LM")):
            shadow.step(event, 0, linearization_anchor=background.export_linearization_anchor())
            shadow.condition({"n0": 2})
            self.assertTrue(shadow.window.gaussian_only)
            np.testing.assert_allclose(shadow.window.values.atVector(shadow.ambiguity_keys["n0"]), [2], atol=1e-8)


if __name__ == "__main__":
    unittest.main()
