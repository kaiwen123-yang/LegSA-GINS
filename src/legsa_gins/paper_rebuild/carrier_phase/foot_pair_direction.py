"""Conditional single-foot-pair direction residual, not a heading observation.

Both body-to-ECEF attitudes are filter-state linearization points, not independent
attitude sensors. Translation and the common rigid lever cancel algebraically.
SDK position provenance, no slip, independence, covariance calibration and
navigation admission are NOT established. No EKF or data reader is implemented.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping, Collection
import numpy as np

from .contact_rotation import FootPositionEpoch, frame_to_frd


class FootPairDirectionError(ValueError):
    pass


def _identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise FootPairDirectionError(name + " requires an explicit nonempty identity")
    return value


def _array(value, shape, name):
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.all(np.isfinite(a)):
        raise FootPairDirectionError(name + " has invalid shape or nonfinite entries")
    return a


def _skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def _rotation(value, name):
    a = _array(value, (3, 3), name)
    if not np.allclose(a.T @ a, np.eye(3), rtol=0., atol=1e-10) or abs(np.linalg.det(a)-1.) > 1e-10:
        raise FootPairDirectionError(name + " must be SO(3); no normalization")
    return a


def _psd(value):
    a = _array(value, (12, 12), "four-point covariance")
    scale = float(np.linalg.norm(a, 2))
    tolerance = 64. * np.finfo(float).eps * 12 * max(scale, np.finfo(float).tiny)
    if np.max(np.abs(a-a.T)) > tolerance:
        raise FootPairDirectionError("four-point covariance must be symmetric")
    a = .5 * (a+a.T)
    if float(np.linalg.eigvalsh(a)[0]) < -tolerance:
        raise FootPairDirectionError("four-point covariance must be positive semidefinite")
    return a  # No clipping/loading; singular output is allowed, never inverted.


def _readonly(value):
    a = np.array(value, copy=True)
    a.setflags(write=False)
    return a


@dataclass(frozen=True)
class BodyAttitudeLinearization:
    time_s: float
    available_time_s: float
    matrix_body_to_ecef: np.ndarray
    source_id: str
    role: str = field(default="FILTER_STATE_LINEARIZATION_NOT_INDEPENDENT_SENSOR", init=False)

    def __post_init__(self):
        if not all(math.isfinite(t) for t in (self.time_s, self.available_time_s)):
            raise FootPairDirectionError("attitude times must be finite")
        if self.available_time_s < self.time_s:
            raise FootPairDirectionError("attitude availability precedes source time")
        _identity(self.source_id, "attitude source")
        object.__setattr__(self, "matrix_body_to_ecef",
                           _readonly(_rotation(self.matrix_body_to_ecef, "body-to-ECEF attitude")))


@dataclass(frozen=True)
class FootPairDirection:
    interval_start_s: float
    interval_end_s: float
    decision_available_time_s: float
    foot_pair: tuple[str, str]
    endpoint_ids: tuple[str, str]
    contact_tokens: tuple[str, str]
    position_source_id: str
    position_gnss_input_used: bool | None
    covariance_source_id: str
    frame_transform_source_id: str
    attitude_source_ids: tuple[str, str]
    residual_body0_m: np.ndarray
    direction0_ecef_m: np.ndarray
    direction1_ecef_m: np.ndarray
    jacobian_world_current_clone: np.ndarray
    endpoint_jacobian: np.ndarray
    residual_covariance_m2: np.ndarray
    current_null_axis_ecef: np.ndarray
    clone_null_axis_ecef: np.ndarray
    joint_linearization_rank: int
    status: str = field(default="CONDITIONAL_PAIR_DIRECTION_ONLY", init=False)
    per_endpoint_rotational_rank: int = field(default=2, init=False)
    physical_relative_direction_rank: int = field(default=2, init=False)
    covariance_status: str = field(default="CALLER_FOUR_POINT_SIGMA_CONDITIONAL_NOT_CALIBRATED", init=False)
    single_use_check_scope: str = field(default="CALLER_SUPPLIED_CONSUMED_ENDPOINT_IDS_ONLY", init=False)
    endpoint_reuse_detected: bool = field(default=False, init=False)
    imu_statistical_independence_proven: bool = field(default=False, init=False)
    no_slip_proven: bool = field(default=False, init=False)
    absolute_heading_observed: bool = field(default=False, init=False)
    navigation_admission: bool = field(default=False, init=False)
    instantaneous_velocity: bool = field(default=False, init=False)

    def __post_init__(self):
        for key in ("residual_body0_m", "direction0_ecef_m", "direction1_ecef_m",
                    "jacobian_world_current_clone", "endpoint_jacobian", "residual_covariance_m2",
                    "current_null_axis_ecef", "clone_null_axis_ecef"):
            object.__setattr__(self, key, _readonly(getattr(self, key)))


def evaluate_foot_pair_direction(
        previous: FootPositionEpoch, current: FootPositionEpoch, *,
        foot_pair: tuple[str, str],
        attitude0: BodyAttitudeLinearization, attitude1: BodyAttitudeLinearization,
        four_point_covariance,
        foot_frd_to_attitude_body,
        interval_continuous_support: Mapping[str, bool | None],
        endpoint_ids: tuple[str, str],
        consumed_endpoint_ids: Collection[str],
        position_source_id: str,
        position_gnss_input_used: bool | None,
        covariance_source_id: str,
        frame_transform_source_id: str,
        decision_time_s: float | None = None) -> FootPairDirection:
    """Sigma order [p0_i,p0_j,p1_i,p1_j], in each endpoint's ORIGINAL FLU/FRD axes.

    foot_pair order fixes signs; epoch array ordering is matched by identity.
    Residual is d0 - C0.T*C1*d1 in attitude-body0 axes, not ECEF.
    Both angular H blocks use the same C0.T*skew(C1*d1), with -/+ signs
    for current/clone. Common world rotation is null for any residual.
    No foot selection, missing-axis completion, covariance inverse, or admission.
    Repeated endpoints must be tracked externally and passed in consumed IDs.
    Both attitudes must represent the exact endpoint times; historical clone
    linearizations may become available later through filter updates.
    """
    if not isinstance(previous, FootPositionEpoch) or not isinstance(current, FootPositionEpoch):
        raise FootPairDirectionError("FootPositionEpoch inputs required")
    if not isinstance(attitude0, BodyAttitudeLinearization) or not isinstance(attitude1, BodyAttitudeLinearization):
        raise FootPairDirectionError("explicit attitude linearizations required")
    if len(foot_pair) != 2 or len(set(foot_pair)) != 2:
        raise FootPairDirectionError("two distinct ordered foot identities required")
    pair = tuple(_identity(name, "foot") for name in foot_pair)
    if current.time_s <= previous.time_s:
        raise FootPairDirectionError("strictly increasing endpoint times required")
    if (attitude0.time_s, attitude1.time_s) != (previous.time_s, current.time_s):
        raise FootPairDirectionError("attitude and foot endpoint times must match exactly")
    if len(endpoint_ids) != 2:
        raise FootPairDirectionError("two endpoint identities required")
    ids = tuple(_identity(v, "endpoint") for v in endpoint_ids)
    if ids[0] == ids[1]:
        raise FootPairDirectionError("repeated endpoint identity")
    if isinstance(consumed_endpoint_ids, (str, bytes)):
        raise FootPairDirectionError("consumed endpoint identities require a collection")
    consumed = {_identity(v, "consumed endpoint") for v in consumed_endpoint_ids}
    if consumed.intersection(ids):
        raise FootPairDirectionError("repeated consumed endpoint; cannot reuse independent noise")
    if set(interval_continuous_support) != set(pair):
        raise FootPairDirectionError("continuous support must explicitly name exactly the ordered pair")
    if any(interval_continuous_support[name] is not True for name in pair):
        raise FootPairDirectionError("whole-interval support not confirmed")
    tokens = []
    for name in pair:
        if name not in previous.foot_ids or name not in current.foot_ids:
            raise FootPairDirectionError("selected foot missing at endpoint")
        i, j = previous.foot_ids.index(name), current.foot_ids.index(name)
        if previous.stance[i] is not True or current.stance[j] is not True:
            raise FootPairDirectionError("both endpoint stance states must be confirmed")
        a, b = previous.contact_tokens[i], current.contact_tokens[j]
        if a is None or b is None or a != b:
            raise FootPairDirectionError("contact episode unknown or changed")
        tokens.append(a)
    available = max(previous.available_time_s, current.available_time_s,
                    attitude0.available_time_s, attitude1.available_time_s)
    decision = available if decision_time_s is None else float(decision_time_s)
    if not math.isfinite(decision) or decision < available:
        raise FootPairDirectionError("decision uses future/unavailable input")
    for value, name in ((position_source_id, "position source"), (covariance_source_id, "covariance source"),
                        (frame_transform_source_id, "frame transform source")):
        _identity(value, name)
    if position_gnss_input_used is not None and type(position_gnss_input_used) is not bool:
        raise FootPairDirectionError("position GNSS-input declaration must be bool or None")
    mount = _rotation(foot_frd_to_attitude_body, "foot-FRD to attitude-body transform")
    f0, f1 = mount @ frame_to_frd(previous.frame), mount @ frame_to_frd(current.frame)
    c0, c1 = attitude0.matrix_body_to_ecef, attitude1.matrix_body_to_ecef
    p0 = [previous.positions_m[previous.foot_ids.index(name)] for name in pair]
    p1 = [current.positions_m[current.foot_ids.index(name)] for name in pair]
    u0, u1 = c0 @ f0 @ (p0[0]-p0[1]), c1 @ f1 @ (p1[0]-p1[1])
    n0, n1 = math.hypot(*u0), math.hypot(*u1)
    if min(n0, n1) <= 1e-10 or not all(math.isfinite(n) for n in (n0, n1)):
        raise FootPairDirectionError("zero or numerically degenerate foot-pair separation")
    # Relative body0 residual preserves common-world-rotation gauge even off
    # the zero-residual manifold; a world-residual Jacobian need not do so.
    relative = c0.T @ c1
    v1 = c0.T @ u1
    residual = f0 @ (p0[0]-p0[1]) - v1
    angular = c0.T @ _skew(u1)
    h = np.column_stack((-angular, angular))
    l = np.column_stack((f0, -f0, -relative @ f1, relative @ f1))
    q = l @ _psd(four_point_covariance) @ l.T
    q = .5 * (q+q.T)
    if not np.all(np.isfinite(q)):
        raise FootPairDirectionError("nonfinite propagated residual covariance")
    return FootPairDirection(
        previous.time_s, current.time_s, decision, pair, ids, tuple(tokens),
        position_source_id, position_gnss_input_used, covariance_source_id, frame_transform_source_id,
        (attitude0.source_id, attitude1.source_id), residual, u0, u1, h, l, q,
        u1/n1, u1/n1, int(np.linalg.matrix_rank(h, tol=n1*1e-10)))


def direction_jacobian_current_ned(result: FootPairDirection, *,
                                   ecef_from_current_ned, ned_frame_connection_per_m):
    """Return 3x24 H: current 21 [P,V,PHI,...], then ECEF clone attitude 3.

    E and K must match the current BLH retraction. K[:,j] is
    vee((dE/dBLH * DRi[:,j]) E.T); caller binds their Earth/source identity.
    """
    if not isinstance(result, FootPairDirection):
        raise FootPairDirectionError("explicit pair-direction result required")
    e = _rotation(ecef_from_current_ned, "ECEF-from-NED")
    k = _array(ned_frame_connection_per_m, (3, 3), "NED frame connection")
    world = result.jacobian_world_current_clone
    h = np.zeros((3, 24))
    h[:, :3] = -world[:, :3] @ k
    h[:, 6:9] = world[:, :3] @ e
    h[:, 21:24] = world[:, 3:]
    return h


def clone_attitude_augmentation_jacobian(*, ecef_from_ned, ned_frame_connection_per_m):
    """ECEF clone error = -K*current_position_error + E*current_phi_error."""
    e = _rotation(ecef_from_ned, "ECEF-from-NED")
    k = _array(ned_frame_connection_per_m, (3, 3), "NED frame connection")
    j = np.zeros((3, 21))
    j[:, :3], j[:, 6:9] = -k, e
    return j


def left_feedback_reset_jacobian(applied_correction_rad):
    """J_l(a), for Log(Exp(a+epsilon) Exp(-a)); local, not exact posterior.

    Positive left feedback matches this repository. Principal corrections only;
    no covariance reset is performed here and no native filter is changed.
    """
    a = _array(applied_correction_rad, (3,), "applied rotation correction")
    theta = math.hypot(*a)
    if theta >= math.pi:
        raise FootPairDirectionError("reset correction must have norm below pi")
    k = _skew(a)
    t2 = theta*theta
    if theta < 1e-4:
        first = .5-t2/24.+t2*t2/720.
        second = 1./6.-t2/120.+t2*t2/5040.
    else:
        first = (1.-math.cos(theta))/t2
        second = (theta-math.sin(theta))/(theta*t2)
    return np.eye(3)+first*k+second*(k@k)
