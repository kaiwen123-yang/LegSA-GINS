"""Conditional SDK-foot-position contact-rotation proxy; never a heading fix.

The inputs are robot-reported body-relative foot positions, NOT verified raw
encoders. Their internal IMU/estimator dependencies are unknown. Two endpoints
must retain the same reported contact identity. That condition does not prove
no slip.

For a rigid interval, define y=(p1-p0)/dt and m=(p0+p1)/2. The model
    y_i = u + skew(m_i) w
eliminates the common translation u. Its finite-interval parameter is the
Cayley rate w=2*tan(theta/2)*axis/dt, NOT an instantaneous gyro rate. Rotations
at pi are singular; endpoint data do not reveal rotations beyond a principal
interval. Only the observable subspace is returned. No EKF connection, contact
threshold fitting, integer search, acceptance test, or reference reader exists.

Errors in BOTH y and m are included to first order at an explicitly supplied
working w. The estimate does not refit that noise model. Reported covariance is
conditional on the working endpoint covariance, linearization and no-slip
assumptions; it is not calibrated and does not prove IMU independence.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence
import numpy as np


class ContactRotationError(ValueError):
    pass


def skew(v: Sequence[float]) -> np.ndarray:
    x, y, z = _vector(v, "vector")
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def _vector(v, name):
    a = np.asarray(v, dtype=float)
    if a.shape != (3,) or not np.all(np.isfinite(a)):
        raise ContactRotationError(name + " must be a finite length-three vector")
    return a


def frame_to_frd(frame: str) -> np.ndarray:
    if frame == "FRD":
        return np.eye(3)
    if frame == "FLU":
        return np.diag([1., -1., -1.])
    raise ContactRotationError("frame must explicitly be FLU or FRD")


def _spd(q, size, name):
    a = np.asarray(q, dtype=float)
    if a.shape != (size, size) or not np.all(np.isfinite(a)):
        raise ContactRotationError(name + " shape or finite-value failure")
    if not np.allclose(a, a.T, rtol=1e-12, atol=1e-15):
        raise ContactRotationError(name + " must be symmetric")
    a = (a + a.T) * .5
    try:
        np.linalg.cholesky(a)
    except np.linalg.LinAlgError as exc:
        raise ContactRotationError(name + " must be positive definite; no flooring") from exc
    return a


@dataclass(frozen=True)
class FootPositionEpoch:
    """Contact tokens identify continuous stance episodes, not just leg names.

    endpoint covariance is supplied separately in original array ordering.
    available_time_s is an explicit replay assumption if only message stamps
    are recorded. No hardware timing calibration is inferred.
    """
    time_s: float
    available_time_s: float
    foot_ids: tuple[str, ...]
    positions_m: np.ndarray
    stance: tuple[bool | None, ...]
    contact_tokens: tuple[str | None, ...]
    frame: str

    def __post_init__(self):
        if not math.isfinite(self.time_s) or not math.isfinite(self.available_time_s):
            raise ContactRotationError("finite time and availability required")
        if self.available_time_s < self.time_s:
            raise ContactRotationError("availability cannot precede source time")
        n = len(self.foot_ids)
        if not n or len(set(self.foot_ids)) != n or any(not isinstance(i, str) or not i for i in self.foot_ids):
            raise ContactRotationError("unique nonempty foot identities required")
        if len(self.stance) != n or len(self.contact_tokens) != n:
            raise ContactRotationError("stance/contact-token dimensions")
        if any(x is not None and type(x) is not bool for x in self.stance):
            raise ContactRotationError("stance must be explicit bool or None")
        if any(x is not None and (not isinstance(x, str) or not x) for x in self.contact_tokens):
            raise ContactRotationError("contact tokens must be nonempty strings or None")
        p = np.asarray(self.positions_m, dtype=float)
        if p.shape != (n, 3) or not np.all(np.isfinite(p)):
            raise ContactRotationError("finite Nx3 positions required")
        frame_to_frd(self.frame)
        p = p.copy()
        p.setflags(write=False)
        object.__setattr__(self, "positions_m", p)
        for name in ("foot_ids", "stance", "contact_tokens"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True)
class ContactRotationProxy:
    status: str
    interval_start_s: float
    interval_end_s: float
    decision_available_time_s: float
    dt_s: float
    foot_ids: tuple[str, ...]
    excluded_feet: Mapping[str, tuple[str, ...]]
    rank: int
    observable_basis_frd: np.ndarray
    nullspace_frd: np.ndarray
    observable_cayley_rate_coordinates_rad_s: np.ndarray
    observable_coordinate_covariance_rad2_s2: np.ndarray
    # This is only a representative; NEVER a full 3D estimate when rank < 3.
    minimum_norm_cayley_rate_frd_rad_s: np.ndarray | None
    observable_information_s2_rad2: np.ndarray
    principal_rotation_vector_frd_rad: np.ndarray | None
    residual_cost_working_model: float | None
    residual_dof: int | None
    residual_covariance_m2_s2: np.ndarray | None
    endpoint_residual_jacobian: np.ndarray | None
    linearization_cayley_rate_frd_rad_s: np.ndarray
    translation_nuisance_representative_frd_mps: np.ndarray | None
    singular_values: np.ndarray
    rank_cutoff: float | None
    source_role: str = "SDK_POSITION_DERIVED_CONTACT_ROTATION_PROXY"
    parameterization: str = "FINITE_INTERVAL_CAYLEY_RATE_NOT_INSTANTANEOUS_GYRO"
    output_frame: str = "FRD"
    uncertainty_status: str = "CONDITIONAL_FIRST_ORDER_ENDPOINT_WORKING_MODEL_NOT_CALIBRATED"
    imu_independence_claim: bool = False
    known_contact_does_not_prove_no_slip: bool = True
    absolute_heading_observed: bool = False
    navigation_admission: bool = False


def endpoint_residual_jacobian(dt_s: float, cayley_rate_frd_rad_s, foot_count: int) -> np.ndarray:
    """For r=(p1-p0)/dt-u-skew((p0+p1)/2)w, columns are [all p0, all p1].

    J0=-I/dt+skew(w)/2 and J1=I/dt+skew(w)/2. The plus skew sign
    follows -skew(delta_m)w=skew(w)delta_m. This covers noisy geometry
    at the given w; it is not an exact nonlinear errors-in-variables likelihood.
    """
    if not math.isfinite(dt_s) or dt_s <= 0:
        raise ContactRotationError("positive finite dt required")
    if type(foot_count) is not int or foot_count < 1:
        raise ContactRotationError("positive integer foot count required")
    w = _vector(cayley_rate_frd_rad_s, "linearization rate")
    j0 = -np.eye(3) / dt_s + .5 * skew(w)
    j1 = np.eye(3) / dt_s + .5 * skew(w)
    return np.column_stack((np.kron(np.eye(foot_count), j0),
                            np.kron(np.eye(foot_count), j1)))


def endpoint_residual_covariance(endpoint_covariance_m2, dt_s: float,
                                 cayley_rate_frd_rad_s, foot_count: int):
    """Input covariance must include all declared cross-foot/time correlations."""
    sigma = _spd(endpoint_covariance_m2, 6 * foot_count, "endpoint covariance")
    j = endpoint_residual_jacobian(dt_s, cayley_rate_frd_rad_s, foot_count)
    q = _spd(j @ sigma @ j.T, 3 * foot_count, "propagated residual covariance")
    return q, j


def cayley_to_principal_rotation_vector(cayley_rate_frd_rad_s, dt_s: float) -> np.ndarray:
    """Principal body1-to-body0 rotation; cannot recover hidden full turns."""
    if not math.isfinite(dt_s) or dt_s <= 0:
        raise ContactRotationError("positive finite dt required")
    w = _vector(cayley_rate_frd_rad_s, "Cayley rate")
    n = math.hypot(*map(float, w))
    if not math.isfinite(n):
        raise ContactRotationError("Cayley magnitude exceeds finite numeric domain")
    if n == 0:
        return np.zeros(3)
    theta = 2. * math.atan(.5 * dt_s * n)
    return theta * (w / n)


def estimate_contact_rotation(previous: FootPositionEpoch, current: FootPositionEpoch,
                              endpoint_covariance_m2, *,
                              linearization_cayley_rate_frd_rad_s,
                              interval_continuous_support: Mapping[str, bool | None],
                              decision_time_s: float | None = None,
                              known_slipping_feet: Sequence[str] = (),
                              rank_relative_tolerance: float = 1e-10) -> ContactRotationProxy:
    """Past-only two-endpoint proxy, with common translation profiled by full-Q GLS.

    Covariance order: [previous feet in its order, current feet in its order],
    each expressed in that endpoint's explicit frame. Both foot-ID sets must
    match; only common stance with unchanged, nonempty contact tokens is used.
    interval_continuous_support must explicitly confirm each whole interval
    using a causal external contact-arc state machine; endpoint stance alone
    is insufficient. This is a reported proxy, not a no-slip certification.
    known_slipping_feet excludes externally declared failures. Unreported slip
    can masquerade as a valid rotation and is not autonomously detected here.
    """
    dt = current.time_s - previous.time_s
    if not math.isfinite(dt) or dt <= 0:
        raise ContactRotationError("strictly increasing endpoint time required")
    if current.available_time_s < previous.available_time_s:
        raise ContactRotationError("availability must be monotonic")
    available = max(current.time_s, current.available_time_s, previous.available_time_s)
    decision = available if decision_time_s is None else float(decision_time_s)
    if not math.isfinite(decision) or decision < available:
        raise ContactRotationError("past-only decision time must cover both endpoints")
    if set(previous.foot_ids) != set(current.foot_ids):
        raise ContactRotationError("endpoint foot-ID sets must match")
    if not math.isfinite(rank_relative_tolerance) or not 0 < rank_relative_tolerance < 1:
        raise ContactRotationError("rank tolerance must be in (0,1)")
    if set(interval_continuous_support) != set(previous.foot_ids):
        raise ContactRotationError("continuous-support mapping must name every foot")
    if any(v is not None and type(v) is not bool for v in interval_continuous_support.values()):
        raise ContactRotationError("continuous support must be explicit bool or None")
    slips = set(known_slipping_feet)
    if not slips.issubset(previous.foot_ids):
        raise ContactRotationError("unknown slipping foot identity")
    n = len(previous.foot_ids)
    full_sigma = _spd(endpoint_covariance_m2, 6 * n, "endpoint covariance")
    wlin = _vector(linearization_cayley_rate_frd_rad_s, "linearization rate").copy()
    mapping = {name: i for i, name in enumerate(current.foot_ids)}
    indices0, indices1, kept, excluded = [], [], [], {}
    for i, name in enumerate(previous.foot_ids):
        k = mapping[name]
        reasons = []
        if previous.stance[i] is not True:
            reasons.append("PREVIOUS_STANCE_UNKNOWN_OR_FALSE")
        if current.stance[k] is not True:
            reasons.append("CURRENT_STANCE_UNKNOWN_OR_FALSE")
        if previous.contact_tokens[i] is None or current.contact_tokens[k] is None:
            reasons.append("CONTACT_IDENTITY_UNKNOWN")
        elif previous.contact_tokens[i] != current.contact_tokens[k]:
            reasons.append("CONTACT_EPISODE_CHANGED")
        if interval_continuous_support[name] is not True:
            reasons.append("INTERVAL_SUPPORT_NOT_CONFIRMED_CONTINUOUS")
        if name in slips:
            reasons.append("EXPLICIT_SLIP")
        if reasons:
            excluded[name] = tuple(reasons)
        else:
            indices0.extend(range(3 * i, 3 * i + 3))
            indices1.extend(range(3 * k, 3 * k + 3))
            kept.append(name)
    common = dict(interval_start_s=previous.time_s, interval_end_s=current.time_s,
                  decision_available_time_s=decision, dt_s=dt, foot_ids=tuple(kept),
                  excluded_feet=excluded, linearization_cayley_rate_frd_rad_s=wlin)
    def unavailable(status):
        return ContactRotationProxy(status=status, rank=0,
            observable_basis_frd=np.empty((3, 0)), nullspace_frd=np.eye(3),
            observable_cayley_rate_coordinates_rad_s=np.empty(0),
            observable_coordinate_covariance_rad2_s2=np.empty((0, 0)),
            minimum_norm_cayley_rate_frd_rad_s=None,
            observable_information_s2_rad2=np.zeros((3, 3)),
            principal_rotation_vector_frd_rad=None, residual_cost_working_model=None,
            residual_dof=None, residual_covariance_m2_s2=None,
            endpoint_residual_jacobian=None,
            translation_nuisance_representative_frd_mps=None,
            singular_values=np.empty(0), rank_cutoff=None, **common)
    if not kept:
        return unavailable("UNAVAILABLE_NO_COMMON_STANCE")
    if len(kept) < 2:
        return unavailable("UNAVAILABLE_SINGLE_STANCE")
    k = len(kept)
    f0, f1 = frame_to_frd(previous.frame), frame_to_frd(current.frame)
    p0 = (previous.positions_m.reshape(-1)[indices0].reshape(k, 3) @ f0.T)
    p1 = (current.positions_m.reshape(-1)[indices1].reshape(k, 3) @ f1.T)
    select = indices0 + [3 * n + i for i in indices1]
    transform = np.zeros((6 * k, 6 * k))
    transform[:3*k, :3*k] = np.kron(np.eye(k), f0)
    transform[3*k:, 3*k:] = np.kron(np.eye(k), f1)
    sigma = transform @ full_sigma[np.ix_(select, select)] @ transform.T
    q, jac = endpoint_residual_covariance(sigma, dt, wlin, k)
    chol = np.linalg.cholesky(q)
    y = ((p1 - p0) / dt).reshape(-1)
    h = np.vstack([skew(p) for p in .5 * (p0 + p1)])
    t = np.tile(np.eye(3), (k, 1))
    yw, hw, tw = (np.linalg.solve(chol, v) for v in (y, h, t))
    qt, _ = np.linalg.qr(tw, mode="complete")
    complement = qt[:, 3:].T
    projected_h, projected_y = complement @ hw, complement @ yw
    u, s, vt = np.linalg.svd(projected_h, full_matrices=True)
    # Scale against endpoint geometry too: a pi rotation can collapse midpoints.
    endpoint_hw = [np.linalg.solve(chol, np.vstack([skew(p) for p in ps]))
                   for ps in (p0, p1)]
    original_scales = [np.linalg.norm(complement @ value, 2) for value in endpoint_hw]
    reference_scale = max(float(s[0]) if len(s) else 0., *map(float, original_scales))
    # Projection of exactly coincident feet is zero mathematically, but its
    # roundoff must not become its own relative scale and appear observable.
    floating_point_scale = max(float(np.linalg.norm(value, 2))
                               for value in (hw, *endpoint_hw))
    cutoff = max(rank_relative_tolerance * reference_scale,
                 64. * np.finfo(float).eps * floating_point_scale)
    rank = int(np.sum(s > cutoff)) if reference_scale > 0 else 0
    basis = vt[:rank].T
    nullspace = vt[rank:].T
    coords = (u[:, :rank].T @ projected_y) / s[:rank]
    representative = basis @ coords
    covariance = np.diag(1. / s[:rank]**2)
    info = (basis * s[:rank]**2) @ basis.T
    nuisance = np.linalg.lstsq(tw, yw - hw @ representative, rcond=None)[0]
    residual = yw - hw @ representative - tw @ nuisance
    if not (np.all(np.isfinite(coords)) and np.all(np.isfinite(covariance)) and np.all(np.isfinite(residual))):
        raise ContactRotationError("nonfinite conditional GLS output")
    return ContactRotationProxy(
        status=("AVAILABLE_FULL_ROTATION_PROXY" if rank == 3 else
                "AVAILABLE_PARTIAL_ROTATION_PROXY" if rank else
                "UNAVAILABLE_DEGENERATE_GEOMETRY"),
        rank=rank, observable_basis_frd=basis, nullspace_frd=nullspace,
        observable_cayley_rate_coordinates_rad_s=coords,
        observable_coordinate_covariance_rad2_s2=covariance,
        minimum_norm_cayley_rate_frd_rad_s=representative if rank else None,
        observable_information_s2_rad2=info,
        principal_rotation_vector_frd_rad=(cayley_to_principal_rotation_vector(representative, dt) if rank == 3 else None),
        residual_cost_working_model=float(residual @ residual),
        residual_dof=3*k-3-rank, residual_covariance_m2_s2=q,
        endpoint_residual_jacobian=jac,
        translation_nuisance_representative_frd_mps=nuisance,
        singular_values=s, rank_cutoff=cutoff, **common)
