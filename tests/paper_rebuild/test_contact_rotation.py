"""Synthetic physics/unit tests only. No measured data, thresholds or filters."""
import math
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.contact_rotation import (
    ContactRotationError, FootPositionEpoch, cayley_to_principal_rotation_vector,
    endpoint_residual_covariance, endpoint_residual_jacobian,
    estimate_contact_rotation, frame_to_frd, skew,
)

POINTS = np.array([[.3, .2, .45], [.3, -.2, .45],
                   [-.3, .2, .45], [-.3, -.2, .45]])
IDS = ("FR", "FL", "RR", "RL")


def rotation(axis, theta):
    # Independent Rodrigues construction, not the estimator's Cayley algebra.
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    cross = np.array([[0., -axis[2], axis[1]], [axis[2], 0., -axis[0]],
                      [-axis[1], axis[0], 0.]])
    return np.eye(3) + np.sin(theta) * cross + (1 - np.cos(theta)) * cross @ cross


def epoch(p, time, *, frame="FRD", ids=None, stance=None, tokens=None, available=None):
    n = len(p)
    ids = IDS[:n] if ids is None else ids
    return FootPositionEpoch(time, time if available is None else available, ids, p,
                             (True,) * n if stance is None else stance,
                             tuple(i + ":episode0" for i in ids) if tokens is None else tokens,
                             frame)


def interval(points=POINTS, theta=.7, axis=(.2, -.3, .8), dt=.04):
    unit = np.asarray(axis) / np.linalg.norm(axis)
    r = rotation(unit, theta)
    shift = np.array([.08, -.02, .01])
    p1 = (points - shift) @ r
    w = 2 * np.tan(theta / 2) * unit / dt
    return epoch(points, 1.), epoch(p1, 1. + dt), w, theta * unit


def estimate(a, b, q=None, w=None, **kwargs):
    n = len(a.foot_ids)
    q = np.eye(6 * n) * 1e-6 if q is None else q
    w = np.zeros(3) if w is None else w
    continuity = kwargs.pop("interval_continuous_support", dict.fromkeys(a.foot_ids, True))
    return estimate_contact_rotation(a, b, q, linearization_cayley_rate_frd_rad_s=w,
                                     interval_continuous_support=continuity, **kwargs)


def test_finite_rotation_and_translation_recovered_as_cayley_not_gyro():
    a, b, w, vector = interval()
    out = estimate(a, b, w=w)
    assert out.rank == 3
    np.testing.assert_allclose(out.minimum_norm_cayley_rate_frd_rad_s, w, atol=1e-11)
    np.testing.assert_allclose(out.principal_rotation_vector_frd_rad, vector, atol=1e-12)
    assert np.linalg.norm(w - vector / out.dt_s) > .7
    assert out.residual_cost_working_model < 1e-20
    assert out.residual_dof == 6
    assert out.parameterization == "FINITE_INTERVAL_CAYLEY_RATE_NOT_INSTANTANEOUS_GYRO"
    assert not out.imu_independence_claim
    assert not out.navigation_admission
    assert not out.absolute_heading_observed


def test_common_translation_is_profiled_out():
    a, b = epoch(POINTS, 0.), epoch(POINTS + [.1, -.2, .05], .1)
    out = estimate(a, b)
    np.testing.assert_allclose(out.minimum_norm_cayley_rate_frd_rad_s, 0, atol=1e-13)
    np.testing.assert_allclose(out.translation_nuisance_representative_frd_mps, [1, -2, .5])
    assert out.residual_cost_working_model < 1e-20


def test_two_contacts_expose_null_axis_and_no_full_rotation():
    a, b, w, _ = interval(points=POINTS[:2])
    out = estimate(a, b, w=w)
    assert out.rank == 2
    assert out.nullspace_frd.shape == (3, 1)
    assert out.observable_coordinate_covariance_rad2_s2.shape == (2, 2)
    assert out.principal_rotation_vector_frd_rad is None
    dmid = .5 * ((a.positions_m[1] - a.positions_m[0]) +
                 (b.positions_m[1] - b.positions_m[0]))
    np.testing.assert_allclose(np.cross(dmid, out.nullspace_frd[:, 0]), 0, atol=1e-13)
    error = w - out.minimum_norm_cayley_rate_frd_rad_s
    np.testing.assert_allclose(out.observable_basis_frd.T @ error, 0, atol=1e-11)
    np.testing.assert_allclose(out.observable_information_s2_rad2 @ out.nullspace_frd,
                               0, atol=1e-9)
    assert out.residual_dof == 1


def test_collinear_contacts_remain_rank_two():
    points = np.array([[-.3, 0, .4], [0, 0, .4], [.3, 0, .4]])
    a, b, w, _ = interval(points=points)
    out = estimate(a, b, w=w)
    assert out.rank == 2
    assert out.principal_rotation_vector_frd_rad is None


def test_noncollinear_three_contacts_observe_three_components():
    a, b, w, _ = interval(points=POINTS[:3])
    out = estimate(a, b, w=w)
    assert out.rank == 3
    np.testing.assert_allclose(out.minimum_norm_cayley_rate_frd_rad_s, w, atol=1e-11)


def test_coincident_contacts_are_unavailable_not_zero_uncertainty():
    p = np.tile([.3, .2, .4], (4, 1))
    out = estimate(epoch(p, 0), epoch(p + [.02, .03, .01], .1))
    assert out.rank == 0
    assert out.minimum_norm_cayley_rate_frd_rad_s is None
    assert out.status == "UNAVAILABLE_DEGENERATE_GEOMETRY"


def test_exact_pi_midpoint_degeneracy_is_exposed():
    a, b, _, _ = interval(theta=math.pi, axis=(0, 0, 1))
    out = estimate(a, b)
    assert out.rank == 0
    assert out.principal_rotation_vector_frd_rad is None
    assert out.residual_cost_working_model > 1e5


def test_endpoint_jacobian_includes_noisy_midpoint_and_matches_finite_difference():
    rng = np.random.default_rng(1007)
    k, dt = 3, .07
    p = rng.normal(size=6 * k)
    w = np.array([2.3, -1.2, .8])
    u = np.array([.2, -.4, .7])
    def residual(x):
        p0, p1 = x[:3*k].reshape(k, 3), x[3*k:].reshape(k, 3)
        return ((p1 - p0) / dt - u - np.cross((p0 + p1) / 2, w)).reshape(-1)
    eps = 1e-6
    fd = np.column_stack([(residual(p + eps * np.eye(6*k)[j]) -
                           residual(p - eps * np.eye(6*k)[j])) / (2 * eps)
                          for j in range(6*k)])
    jac = endpoint_residual_jacobian(dt, w, k)
    np.testing.assert_allclose(jac, fd, atol=4e-9)
    # The geometry contribution has the same sign at both endpoints.
    np.testing.assert_allclose(jac[:, :3*k] + jac[:, 3*k:], np.kron(np.eye(k), skew(w)))


def test_correlated_endpoint_propagation_keeps_cross_time_and_cross_foot_terms():
    rng = np.random.default_rng(2026)
    z = rng.normal(size=(18, 18))
    sigma = (z @ z.T + np.eye(18)) * 1e-8
    w = np.array([1.1, .3, -.7])
    q, jac = endpoint_residual_covariance(sigma, .05, w, 3)
    np.testing.assert_allclose(q, jac @ sigma @ jac.T, rtol=1e-13)
    diagonalized, _ = endpoint_residual_covariance(np.diag(np.diag(sigma)), .05, w, 3)
    assert np.linalg.norm(q - diagonalized) > .2 * np.linalg.norm(q)
    q_zero, _ = endpoint_residual_covariance(sigma, .05, np.zeros(3), 3)
    assert not np.allclose(q, q_zero, atol=1e-10)


def test_full_q_nuisance_projection_matches_independent_shared_foot_difference_gls():
    rng = np.random.default_rng(3456)
    a, b, w, _ = interval(theta=.3)
    noise = rng.normal(size=(4, 3)) * .002
    b = epoch(b.positions_m + noise, b.time_s)
    z = rng.normal(size=(24, 24))
    sigma = (z @ z.T + np.eye(24)) * 1e-7
    out = estimate(a, b, q=sigma, w=w)
    dt = b.time_s - a.time_s
    y = ((b.positions_m - a.positions_m) / dt).reshape(-1)
    h = np.vstack([skew(p) for p in (a.positions_m + b.positions_m) / 2])
    d = np.zeros((9, 12))
    for i in range(3):
        d[3*i:3*i+3, :3] = -np.eye(3)
        d[3*i:3*i+3, 3*(i+1):3*(i+2)] = np.eye(3)
    qd = d @ out.residual_covariance_m2_s2 @ d.T
    hd, yd = d @ h, d @ y
    info = hd.T @ np.linalg.solve(qd, hd)
    expected = np.linalg.solve(info, hd.T @ np.linalg.solve(qd, yd))
    np.testing.assert_allclose(out.minimum_norm_cayley_rate_frd_rad_s, expected, atol=1e-11)
    np.testing.assert_allclose(out.observable_information_s2_rad2, info, rtol=1e-12, atol=1e-10)
    assert np.linalg.norm(qd[:3, 3:6]) > 1e-5
    wrong_info = hd.T @ np.linalg.solve(np.diag(np.diag(qd)), hd)
    assert np.linalg.norm(info - wrong_info) > .1 * np.linalg.norm(info)


def test_frame_conversion_and_current_order_preserve_result_and_full_q():
    rng = np.random.default_rng(90)
    a, b, w, _ = interval()
    z = rng.normal(size=(24, 24))
    sigma = (z @ z.T + np.eye(24)) * 1e-7
    baseline = estimate(a, b, sigma, w)
    order = [2, 0, 3, 1]
    f = np.diag([1., -1., -1.])
    a_flu = epoch(a.positions_m @ f, a.time_s, frame="FLU")
    ids = tuple(IDS[i] for i in order)
    b_flu = epoch(b.positions_m[order] @ f, b.time_s, frame="FLU", ids=ids)
    permutation = np.eye(12)[np.array([[3*i, 3*i+1, 3*i+2] for i in order]).ravel()]
    transform = np.zeros((24, 24))
    transform[:12, :12] = np.kron(np.eye(4), f)
    transform[12:, 12:] = permutation @ np.kron(np.eye(4), f)
    reordered_sigma = transform @ sigma @ transform.T
    out = estimate(a_flu, b_flu, reordered_sigma, w)
    np.testing.assert_allclose(out.minimum_norm_cayley_rate_frd_rad_s,
                               baseline.minimum_norm_cayley_rate_frd_rad_s, atol=1e-11)
    np.testing.assert_allclose(out.residual_covariance_m2_s2,
                               baseline.residual_covariance_m2_s2, atol=1e-14)


def test_contact_changes_unknown_support_and_reported_slip_exclude_feet():
    a, b, _, _ = interval()
    b = epoch(b.positions_m, b.time_s,
              stance=(True, True, None, True),
              tokens=("FR:episode1", "FL:episode0", "RR:episode0", "RL:episode0"))
    out = estimate(a, b, known_slipping_feet=("FL",),
                   interval_continuous_support={"FR": True, "FL": True, "RR": True, "RL": None})
    assert out.status == "UNAVAILABLE_NO_COMMON_STANCE"
    assert "CONTACT_EPISODE_CHANGED" in out.excluded_feet["FR"]
    assert "EXPLICIT_SLIP" in out.excluded_feet["FL"]
    assert "CURRENT_STANCE_UNKNOWN_OR_FALSE" in out.excluded_feet["RR"]
    assert "INTERVAL_SUPPORT_NOT_CONFIRMED_CONTINUOUS" in out.excluded_feet["RL"]


def test_endpoint_stance_true_is_insufficient_without_interval_confirmation():
    a, b, _, _ = interval()
    continuity = dict.fromkeys(IDS, False)
    continuity["FR"] = True
    out = estimate(a, b, interval_continuous_support=continuity)
    assert out.status == "UNAVAILABLE_SINGLE_STANCE"
    assert out.foot_ids == ("FR",)
    assert out.observable_coordinate_covariance_rad2_s2.shape == (0, 0)
    assert out.minimum_norm_cayley_rate_frd_rad_s is None


def test_undeclared_rigid_slip_can_mimic_rotation_is_not_claimed_detected():
    # Body is actually fixed; a moving support platform rotates all reported feet.
    # The same positions also admit stationary-world-feet/body-rotation interpretation.
    a, b, w, _ = interval(theta=.04)
    out = estimate(a, b, w=w)
    assert out.rank == 3
    assert out.residual_cost_working_model < 1e-20
    assert out.known_contact_does_not_prove_no_slip
    assert not out.imu_independence_claim
    assert not out.navigation_admission


def test_output_is_available_at_current_receipt_never_interval_midpoint():
    a = epoch(POINTS, 1., available=1.01)
    b = epoch(POINTS, 1.1, available=1.14)
    out = estimate(a, b)
    assert out.decision_available_time_s == 1.14
    with pytest.raises(ContactRotationError, match="past-only"):
        estimate(a, b, decision_time_s=1.13)


@pytest.mark.parametrize("dt", [0, -.1, float("nan"), float("inf")])
def test_jacobian_rejects_invalid_dt(dt):
    with pytest.raises(ContactRotationError):
        endpoint_residual_jacobian(dt, [0, 0, 0], 2)


def test_time_identity_and_input_guards():
    a, b, _, _ = interval()
    with pytest.raises(ContactRotationError, match="increasing"):
        estimate(b, a)
    with pytest.raises(ContactRotationError, match="continuous-support"):
        estimate(a, b, interval_continuous_support={"FR": True})
    with pytest.raises(ContactRotationError, match="positive definite"):
        estimate(a, b, q=np.zeros((24, 24)))
    with pytest.raises(ContactRotationError, match="symmetric"):
        q = np.eye(24)
        q[0, 1] = .2
        estimate(a, b, q=q)
    with pytest.raises(ContactRotationError, match="explicitly"):
        frame_to_frd("body")
    with pytest.raises(ContactRotationError, match="finite"):
        epoch(np.full((4, 3), np.nan), 0)
    with pytest.raises(ContactRotationError, match="precede"):
        epoch(POINTS, 1, available=.9)
    old = epoch(POINTS, 1, available=2)
    new = epoch(POINTS, 1.1, available=1.2)
    with pytest.raises(ContactRotationError, match="monotonic"):
        estimate(old, new)


def test_cayley_zero_and_large_finite_value_are_well_defined():
    np.testing.assert_array_equal(cayley_to_principal_rotation_vector([0, 0, 0], .1), 0)
    v = cayley_to_principal_rotation_vector([1e200, 0, 0], .1)
    np.testing.assert_allclose(v, [math.pi, 0, 0])

def test_snapshot_copies_mutable_input_and_rejects_cayley_norm_overflow():
    p = POINTS.copy()
    ids, stance, tokens = list(IDS), [True] * 4, [i + ":0" for i in IDS]
    state = epoch(p, 1., ids=ids, stance=stance, tokens=tokens)
    p[:] = 0
    ids[0] = "changed"
    stance[0] = False
    tokens[0] = None
    np.testing.assert_array_equal(state.positions_m, POINTS)
    assert state.foot_ids == IDS and all(state.stance)
    assert state.contact_tokens[0] == "FR:0"
    with pytest.raises(ContactRotationError, match="numeric domain"):
        cayley_to_principal_rotation_vector([1.7e308] * 3, .1)
