"""Coordinate and diagnostic algebra only; no native solver or raw reference."""
import numpy as np
from scipy.spatial.transform import Rotation

from legsa_gins.paper_rebuild.hext.hx02d_reference_free import dump, integrate, ols, rpy, wrap
from legsa_gins.paper_rebuild.hext.hx02d_reference_evaluation import align, score


def test_numpy_counters_encode_as_json_scalars(tmp_path):
    import json
    destination = tmp_path / "counts.json"
    dump(destination, {"censored_stance_count": np.int64(2), "finite": np.bool_(True)})
    assert json.loads(destination.read_text()) == {"censored_stance_count": 2, "finite": True}


def test_body_to_world_rpy_order_and_sign():
    angles = np.array([[4., -7., 39.], [-12., 9., -71.]])
    rotations = Rotation.from_euler("xyz", angles, degrees=True).as_matrix()
    np.testing.assert_allclose(np.degrees(rpy(rotations)), angles, atol=1e-12)


def test_contact_velocity_cancels_rotating_stationary_foot():
    omega = np.array([.2, -.1, .5])
    point = np.array([.25, -.15, -.3])
    velocity = np.array([.8, -.1, .02])
    point_rate = -velocity - np.cross(omega, point)
    np.testing.assert_allclose(-(np.cross(omega, point) + point_rate), velocity)


def test_integral_marks_unobserved_intervals():
    t = np.arange(5.)
    v = np.ones((5, 3))
    v[2] = np.nan
    p, gap = integrate(t, v)
    np.testing.assert_allclose(p[-1], [2, 2, 2])
    assert gap["unobserved_interval_count"] == 2
    assert gap["unobserved_duration_s"] == 2


def test_four_dof_alignment_preserves_scale_and_tilt():
    t = np.arange(31.)
    p = np.column_stack((t, np.sin(t), .1*t))
    yaw = 2*t
    Q = Rotation.from_euler("z", 37., degrees=True).as_matrix()
    reference = p @ Q.T + [4, -3, .2]
    fitted, fitted_yaw, result = align(p, yaw, reference, yaw + 37, t <= 10)
    np.testing.assert_allclose(fitted, reference, atol=1e-12)
    np.testing.assert_allclose(fitted_yaw, yaw+37, atol=1e-12)
    assert abs(result["yaw_offset_deg"]-37) < 1e-12
    scaled, _, _ = align(2*p, yaw, reference, yaw+37, t <= 10)
    assert np.max(np.abs(scaled-reference)) > 10


def test_ned_yaw_residual_and_minus_two_regression():
    ref_enu = np.linspace(0, 60, 61)
    estimate_enu = -ref_enu
    ned_turn = -ref_enu
    error = wrap(ref_enu-estimate_enu)
    result = ols(ned_turn, error)
    assert abs(result["slope"] + 2) < 1e-12
    assert abs(result["r2"] - 1) < 1e-12


def test_position_drift_is_slope_not_endpoint_percentage():
    t = np.arange(1., 31.)
    ref = np.column_stack((t, np.zeros_like(t), np.zeros_like(t)))
    estimate = ref + [10, 0, 0]
    value, _, _ = score(estimate, np.zeros_like(t), ref, np.zeros_like(t), t, t)
    assert abs(value["position_drift_m_per_100m"]) < 1e-10
    assert value["endpoint_error_m_per_100m"] > 30
