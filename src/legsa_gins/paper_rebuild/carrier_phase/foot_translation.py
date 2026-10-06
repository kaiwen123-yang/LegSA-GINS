"""GNSS-free-declared conditional foot-interval displacement, not a velocity.

p0 = R p1 + t_body, where R maps body1 FRD into body0 FRD.
R must be supplied in full; a rank-deficient contact-rotation representative is
never completed here. SDK position/contact/gyro sources may be correlated.

All covariance is caller-supplied, first-order and conditional on fixed working
geometry/GLS weights and no slip. No calibrated uncertainty, statistical
independence from an EKF IMU, admission gate or navigation update is claimed.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Mapping
import numpy as np

from .contact_rotation import FootPositionEpoch, frame_to_frd, skew


class FootTranslationError(ValueError):
    pass


def _identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise FootTranslationError(name + " must be an explicit nonempty source identity")
    return value


def _vector(value, name):
    a = np.asarray(value, dtype=float)
    if a.shape != (3,) or not np.all(np.isfinite(a)):
        raise FootTranslationError(name + " must be a finite 3-vector")
    return a


def _rotation(value):
    a = np.asarray(value, dtype=float)
    if a.shape != (3, 3) or not np.all(np.isfinite(a)):
        raise FootTranslationError("finite 3x3 rotation required")
    if not np.allclose(a.T @ a, np.eye(3), rtol=0., atol=1e-10) or abs(np.linalg.det(a) - 1.) > 1e-10:
        raise FootTranslationError("relative rotation must be SO(3); no repair/normalization")
    return a


def _joint_psd(value, dimension):
    sigma = np.asarray(value, dtype=float)
    if sigma.shape != (dimension, dimension) or not np.all(np.isfinite(sigma)):
        raise FootTranslationError("joint covariance has invalid dimensions or nonfinite entries")
    scale = float(np.linalg.norm(sigma, 2))
    tolerance = 64. * np.finfo(float).eps * dimension * max(scale, np.finfo(float).tiny)
    if np.max(np.abs(sigma - sigma.T)) > tolerance:
        raise FootTranslationError("joint covariance must be symmetric")
    sigma = (sigma + sigma.T) * .5
    if float(np.linalg.eigvalsh(sigma)[0]) < -tolerance:
        raise FootTranslationError("joint covariance must be positive semidefinite")
    # No clipping, loading, flooring or fitted covariance.
    return sigma


@dataclass(frozen=True)
class RelativeRotationInterval:
    start_time_s: float
    end_time_s: float
    available_time_s: float
    matrix_body1_to_body0_frd: np.ndarray
    source_id: str
    gnss_free_declared: bool
    fully_specified_rotation_declared: bool
    derived_from_rank_deficient_contact: bool
    perturbation_convention: str
    imu_statistical_independence_proven: bool = field(default=False, init=False)

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.start_time_s, self.end_time_s, self.available_time_s)):
            raise FootTranslationError("rotation interval times must be finite")
        if self.end_time_s <= self.start_time_s or self.available_time_s < self.end_time_s:
            raise FootTranslationError("rotation interval/availability is noncausal")
        _identity(self.source_id, "rotation source")
        if self.gnss_free_declared is not True:
            raise FootTranslationError("GNSS-free rotation provenance must be declared")
        if self.fully_specified_rotation_declared is not True or self.derived_from_rank_deficient_contact is not False:
            raise FootTranslationError("full relative rotation required; no rank-deficient completion")
        if self.perturbation_convention != "LEFT_BODY0_FRD":
            raise FootTranslationError("explicit LEFT_BODY0_FRD perturbation convention required")
        r = _rotation(self.matrix_body1_to_body0_frd).copy()
        r.setflags(write=False)
        object.__setattr__(self, "matrix_body1_to_body0_frd", r)


@dataclass(frozen=True)
class FootIntervalTranslation:
    status: str
    interval_start_s: float
    interval_end_s: float
    available_time_s: float
    dt_s: float
    foot_ids: tuple[str, ...]
    excluded_feet: Mapping[str, tuple[str, ...]]
    position_source_id: str
    rotation_source_id: str
    lever_source_id: str
    covariance_source_id: str
    imu_lever_body_frd_m: np.ndarray
    body_origin_displacement_body0_frd_m: np.ndarray | None
    imu_point_displacement_body0_frd_m: np.ndarray | None
    body_imu_joint_covariance_m2: np.ndarray | None
    body_imu_joint_jacobian: np.ndarray | None
    per_foot_displacements_body0_frd_m: np.ndarray | None
    per_foot_covariance_m2: np.ndarray | None
    measurement_jacobian_original_joint_coordinates: np.ndarray | None
    gls_mean_matrix: np.ndarray | None
    residuals_body0_frd_m: np.ndarray | None
    residual_cost_working_model: float | None
    residual_dof: int | None
    conditional_translation_rank: int
    source_role: str = "SDK_FOOT_POSITION_CONDITIONAL_INTERVAL_DISPLACEMENT"
    output_measurand: str = "FINITE_INTERVAL_DISPLACEMENT_NOT_CURRENT_VELOCITY"
    uncertainty_status: str = "CALLER_SIGMA_FIRST_ORDER_FIXED_WORKING_LINEARIZATION_NOT_CALIBRATED"
    gnss_free_provenance_declared: bool = True
    imu_statistical_independence_proven: bool = False
    no_slip_proven: bool = False
    common_slip_observable: bool = False
    navigation_admission: bool = False


def interval_displacement_jacobians(rotation_body1_to_body0_frd,
                                    positions1_frd_m, imu_lever_body_frd_m):
    """Selected-foot order [all p0, all p1, delta_theta_body0, delta_lever].

    y_i=p0_i-R*p1_i: Jp0=I, Jp1=-R, Jtheta=skew(R*p1_i).
    IMU correction (R-I)l: Jtheta=-skew(R*l), Jlever=R-I.
    Left perturbation is R_true=Exp(skew(delta_theta_body0))*R.
    """
    r = _rotation(rotation_body1_to_body0_frd)
    p1 = np.asarray(positions1_frd_m, dtype=float)
    if p1.ndim != 2 or p1.shape[1] != 3 or not len(p1) or not np.all(np.isfinite(p1)):
        raise FootTranslationError("positions1 must be a finite nonempty Nx3 array")
    lever = _vector(imu_lever_body_frd_m, "mandatory IMU lever")
    count = len(p1)
    j = np.zeros((3 * count, 6 * count + 6))
    for index, point in enumerate(p1):
        rows = slice(3 * index, 3 * index + 3)
        j[rows, rows] = np.eye(3)
        j[rows, 3 * count + 3 * index:3 * count + 3 * index + 3] = -r
        j[rows, 6 * count:6 * count + 3] = skew(r @ point)
    correction = np.zeros((3, 6 * count + 6))
    correction[:, 6 * count:6 * count + 3] = -skew(r @ lever)
    correction[:, 6 * count + 3:] = r - np.eye(3)
    return j, correction


def estimate_foot_interval_translation(
        previous: FootPositionEpoch, current: FootPositionEpoch, *,
        relative_rotation: RelativeRotationInterval,
        imu_lever_body_frd_m,
        joint_covariance,
        interval_continuous_support: Mapping[str, bool | None],
        position_source_id: str,
        lever_source_id: str,
        covariance_source_id: str,
        decision_time_s: float | None = None) -> FootIntervalTranslation:
    """Estimate conditional displacement with full-Q GLS, never an EKF update.

    joint_covariance order is all previous-foot position errors in their input
    frame, all current-foot errors in their input frame, LEFT_BODY0_FRD rotation
    error, then rigid-lever error in body FRD. Input foot ordering may differ;
    identity matching transports all cross terms. The mandatory lever points
    from the body origin to the IMU point, expressed in rigid body FRD axes.
    R and its covariance are
    caller-supplied; zero cross blocks do not establish sensor independence.

    The weights and Jacobians stay frozen at the supplied working geometry.
    No derivative of data-dependent GLS weights is claimed. One common foot
    has zero residual degrees of freedom and cannot test slip.
    """
    if not isinstance(previous, FootPositionEpoch) or not isinstance(current, FootPositionEpoch):
        raise FootTranslationError("explicit FootPositionEpoch inputs required")
    if not isinstance(relative_rotation, RelativeRotationInterval):
        raise FootTranslationError("explicit full RelativeRotationInterval required")
    rinput = relative_rotation
    if rinput.start_time_s != previous.time_s or rinput.end_time_s != current.time_s:
        raise FootTranslationError("rotation and foot intervals must match exactly")
    if current.time_s <= previous.time_s or current.available_time_s < previous.available_time_s:
        raise FootTranslationError("foot source times and availability must be monotonic")
    available = max(previous.available_time_s, current.available_time_s, rinput.available_time_s)
    decision = available if decision_time_s is None else float(decision_time_s)
    if not math.isfinite(decision) or decision < available:
        raise FootTranslationError("past-only decision must cover all source availability")
    position_source_id = _identity(position_source_id, "position source")
    lever_source_id = _identity(lever_source_id, "lever source")
    covariance_source_id = _identity(covariance_source_id, "covariance source")
    lever = _vector(imu_lever_body_frd_m, "mandatory IMU lever").copy()
    if set(previous.foot_ids) != set(current.foot_ids):
        raise FootTranslationError("endpoint foot identity sets must agree")
    if (set(interval_continuous_support) != set(previous.foot_ids)
            or any(v is not None and type(v) is not bool for v in interval_continuous_support.values())):
        raise FootTranslationError("explicit bool/None continuous-support mapping required for every foot")
    n = len(previous.foot_ids)
    sigma = _joint_psd(joint_covariance, 6 * n + 6)
    mapping = {name: index for index, name in enumerate(current.foot_ids)}
    selected, excluded = [], {}
    for index0, name in enumerate(previous.foot_ids):
        index1 = mapping[name]
        reasons = []
        if previous.stance[index0] is not True or current.stance[index1] is not True:
            reasons.append("BOTH_ENDPOINT_STANCE_NOT_CONFIRMED")
        if previous.contact_tokens[index0] is None or current.contact_tokens[index1] is None:
            reasons.append("CONTACT_EPISODE_UNKNOWN")
        elif previous.contact_tokens[index0] != current.contact_tokens[index1]:
            reasons.append("CONTACT_EPISODE_CHANGED")
        if interval_continuous_support[name] is not True:
            reasons.append("WHOLE_INTERVAL_SUPPORT_NOT_CONFIRMED")
        if reasons:
            excluded[name] = tuple(reasons)
        else:
            selected.append((name, index0, index1))
    common = dict(
        interval_start_s=previous.time_s, interval_end_s=current.time_s,
        available_time_s=decision, dt_s=current.time_s - previous.time_s,
        foot_ids=tuple(value[0] for value in selected), excluded_feet=excluded,
        position_source_id=position_source_id, rotation_source_id=rinput.source_id,
        lever_source_id=lever_source_id, covariance_source_id=covariance_source_id,
        imu_lever_body_frd_m=lever)
    if not selected:
        return FootIntervalTranslation(status="UNAVAILABLE_NO_CONTINUOUS_SUPPORT",
            body_origin_displacement_body0_frd_m=None, imu_point_displacement_body0_frd_m=None,
            body_imu_joint_covariance_m2=None, body_imu_joint_jacobian=None,
            per_foot_displacements_body0_frd_m=None, per_foot_covariance_m2=None,
            measurement_jacobian_original_joint_coordinates=None, gls_mean_matrix=None,
            residuals_body0_frd_m=None, residual_cost_working_model=None, residual_dof=None,
            conditional_translation_rank=0, **common)
    k = len(selected)
    f0, f1 = frame_to_frd(previous.frame), frame_to_frd(current.frame)
    p0 = np.asarray([f0 @ previous.positions_m[i] for _, i, _ in selected])
    p1 = np.asarray([f1 @ current.positions_m[j] for _, _, j in selected])
    # Maps original joint coordinates into selected FRD coordinates.
    selection = np.zeros((6 * k + 6, 6 * n + 6))
    for index, (_, index0, index1) in enumerate(selected):
        selection[3*index:3*index+3, 3*index0:3*index0+3] = f0
        selection[3*k+3*index:3*k+3*index+3, 3*n+3*index1:3*n+3*index1+3] = f1
    selection[6*k:, 6*n:] = np.eye(6)
    r = rinput.matrix_body1_to_body0_frd
    j_selected, correction_selected = interval_displacement_jacobians(r, p1, lever)
    j = j_selected @ selection
    correction = correction_selected @ selection
    q = j @ sigma @ j.T
    q = (q + q.T) * .5
    if not np.all(np.isfinite(q)):
        raise FootTranslationError("nonfinite propagated per-foot covariance")
    try:
        chol = np.linalg.cholesky(q)
    except np.linalg.LinAlgError as exc:
        raise FootTranslationError("propagated per-foot Q must be positive definite; no flooring") from exc
    measurements = p0 - p1 @ r.T
    y = measurements.reshape(-1)
    t_matrix = np.tile(np.eye(3), (k, 1))
    yw, tw = np.linalg.solve(chol, y), np.linalg.solve(chol, t_matrix)
    orthogonal, upper = np.linalg.qr(tw, mode="reduced")
    try:
        whitening_mean = np.linalg.solve(upper, orthogonal.T)
        mean_matrix = np.linalg.solve(chol.T, whitening_mean.T).T
    except np.linalg.LinAlgError as exc:
        raise FootTranslationError("conditional translation GLS factor is singular") from exc
    displacement = mean_matrix @ y
    residual = measurements - displacement
    whitened_residual = np.linalg.solve(chol, residual.reshape(-1))
    g_body = mean_matrix @ j
    g_imu = g_body + correction
    g = np.vstack((g_body, g_imu))
    joint_output = g @ sigma @ g.T
    joint_output = (joint_output + joint_output.T) * .5
    imu_displacement = displacement + (r - np.eye(3)) @ lever
    if not all(np.all(np.isfinite(value)) for value in
               (displacement, imu_displacement, joint_output, whitened_residual)):
        raise FootTranslationError("nonfinite first-order GLS output")
    return FootIntervalTranslation(status="AVAILABLE_CONDITIONAL_INTERVAL_DISPLACEMENT",
        body_origin_displacement_body0_frd_m=displacement,
        imu_point_displacement_body0_frd_m=imu_displacement,
        body_imu_joint_covariance_m2=joint_output,
        body_imu_joint_jacobian=g,
        per_foot_displacements_body0_frd_m=measurements, per_foot_covariance_m2=q,
        measurement_jacobian_original_joint_coordinates=j, gls_mean_matrix=mean_matrix,
        residuals_body0_frd_m=residual,
        residual_cost_working_model=float(whitened_residual @ whitened_residual),
        residual_dof=3*k-3, conditional_translation_rank=3, **common)
