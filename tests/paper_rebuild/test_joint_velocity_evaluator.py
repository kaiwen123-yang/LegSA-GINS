"""Mathematical checks for the separate offline velocity bridge; no real reference IO."""
from pathlib import Path
import importlib.util
import unittest

import numpy as np
from scipy.spatial.transform import Rotation

PATH = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/evaluate_joint_by2_velocity.py"
SPEC = importlib.util.spec_from_file_location("joint_velocity_evaluator", PATH)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class VelocityBridgeMath(unittest.TestCase):
    def test_point_velocity_is_derivative_of_rigid_point(self):
        rotation = Rotation.from_rotvec([.3, -.2, .6]).as_matrix()
        omega = np.array([.4, .2, -.3])
        lever = np.array([.2, -.1, .3])
        origin_velocity = np.array([1., -.3, .2])
        dt = 1e-5
        forward = rotation @ Rotation.from_rotvec(dt*omega).as_matrix() @ lever
        backward = rotation @ Rotation.from_rotvec(-dt*omega).as_matrix() @ lever
        exact = rotation@origin_velocity + (forward-backward)/(2*dt)
        actual = bridge.reference_imu_velocity(rotation, origin_velocity, omega, lever)
        np.testing.assert_allclose(actual, exact, atol=5e-12, rtol=0.)
        changed_axes = Rotation.from_rotvec([-.5, .1, .2]).as_matrix()
        np.testing.assert_allclose(
            bridge.reference_imu_velocity(changed_axes@rotation, origin_velocity, omega, lever),
            changed_axes@actual, atol=1e-15)

    def test_common_support_and_squared_linear_error_integral(self):
        t = np.arange(4.)
        values = np.array([[0., 0., 0.], [1., 2., -1.],
                           [np.nan]*3, [3., 6., -3.]])
        query = np.arange(0., 3.5, .5)
        interpolated = bridge.interpolated_velocity(t, values, query)
        self.assertTrue(np.isfinite(interpolated[:3]).all())
        self.assertTrue(np.isnan(interpolated[3:6]).all())
        self.assertTrue(np.isfinite(interpolated[-1]).all())
        valid = np.isfinite(interpolated).all(axis=1)
        metrics = bridge.velocity_metrics(query, interpolated, valid[:-1]&valid[1:])
        self.assertEqual(metrics["duration_s"], 1.)
        np.testing.assert_allclose(metrics["rmse_ned_mps"], np.sqrt([1/3,4/3,1/3]))
        self.assertAlmostEqual(metrics["three_d_rmse_mps"], np.sqrt(2.))
        self.assertAlmostEqual(metrics["horizontal_rmse_mps"], np.sqrt(5/3))


if __name__ == "__main__":
    unittest.main()
