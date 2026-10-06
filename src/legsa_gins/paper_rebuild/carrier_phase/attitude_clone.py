"""One 21+3 attitude-clone Gaussian research kernel; no navigation backend.

Supports deterministic cloning, conditional Gaussian updates and local covariance
reset. The nominal navigation state is external. All covariance/noise inputs are
working models: SDK independence, calibration, heading integrity and admission
are never inferred. Singular PSD state covariance is expected after cloning.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
import numpy as np

from .foot_pair_direction import left_feedback_reset_jacobian

CURRENT_DIM = 21
CLONE_DIM = 3
ZERO_CROSS = "DECLARED_ZERO_WORKING_CROSS_COVARIANCE"
SUPPLIED_CROSS = "SUPPLIED_WORKING_CROSS_COVARIANCE"


class AttitudeCloneError(ValueError):
    pass


def _identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise AttitudeCloneError(name + " requires a nonempty identity/note")
    return value


def _array(value, shape, name):
    if np.iscomplexobj(value):
        raise AttitudeCloneError(name + " must be real")
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.all(np.isfinite(a)):
        raise AttitudeCloneError(name + " shape or finite-value failure")
    return a


def _readonly(value):
    a = np.array(value, copy=True)
    a.setflags(write=False)
    return a


def _psd(value, size, name):
    a = _array(value, (size, size), name)
    scale = float(np.linalg.norm(a, 2))
    if not math.isfinite(scale):
        raise AttitudeCloneError(name + " exceeds finite numeric domain")
    tol = 64.*np.finfo(float).eps*size*max(scale, np.finfo(float).tiny)
    if np.max(np.abs(a-a.T)) > tol:
        raise AttitudeCloneError(name + " must be symmetric")
    a = .5*(a+a.T)
    if np.linalg.eigvalsh(a)[0] < -tol:
        raise AttitudeCloneError(name + " must be positive semidefinite")
    return a  # No negative-eigenvalue clipping or loading.


def _notes(old, new):
    return tuple(dict.fromkeys((*old, new)))


@dataclass(frozen=True)
class ErrorGaussian:
    mean: np.ndarray
    covariance: np.ndarray
    current_time_s: float
    initial_source_id: str
    clone_id: str | None = None
    clone_time_s: float | None = None
    used_clone_ids: frozenset[str] = field(default_factory=frozenset)
    consumed_measurement_ids: frozenset[str] = field(default_factory=frozenset)
    working_assumptions: tuple[str, ...] = ()
    physical_calibration_proven: bool = field(default=False, init=False)
    navigation_admission: bool = field(default=False, init=False)

    def __post_init__(self):
        dim = 21 if self.clone_id is None else 24
        if not math.isfinite(self.current_time_s):
            raise AttitudeCloneError("current time must be finite")
        _identity(self.initial_source_id, "initial state source")
        used = frozenset(_identity(v, "used clone") for v in self.used_clone_ids)
        consumed = frozenset(_identity(v, "consumed measurement") for v in self.consumed_measurement_ids)
        if self.clone_id is None:
            if self.clone_time_s is not None:
                raise AttitudeCloneError("inactive clone cannot have a time")
        else:
            _identity(self.clone_id, "clone")
            if self.clone_time_s is None or not math.isfinite(self.clone_time_s) or self.clone_time_s > self.current_time_s:
                raise AttitudeCloneError("invalid/future clone time")
            if self.clone_id not in used:
                raise AttitudeCloneError("active clone must be present in local lifecycle ledger")
        object.__setattr__(self, "mean", _readonly(_array(self.mean, (dim,), "state mean")))
        object.__setattr__(self, "covariance", _readonly(_psd(self.covariance, dim, "state covariance")))
        object.__setattr__(self, "used_clone_ids", used)
        object.__setattr__(self, "consumed_measurement_ids", consumed)
        object.__setattr__(self, "working_assumptions", tuple(self.working_assumptions))

    @property
    def dimension(self):
        return len(self.mean)


@dataclass(frozen=True)
class NoiseCorrelation:
    mode: str
    source_id: str
    qualification_note: str
    cross_covariance: np.ndarray | None = None
    physical_independence_proven: bool = field(default=False, init=False)

    def __post_init__(self):
        if self.mode not in (ZERO_CROSS, SUPPLIED_CROSS):
            raise AttitudeCloneError("explicit supported correlation mode required")
        _identity(self.source_id, "noise source")
        _identity(self.qualification_note, "noise qualification")
        if self.mode == ZERO_CROSS and self.cross_covariance is not None:
            raise AttitudeCloneError("zero-cross mode cannot ignore supplied cross covariance")
        if self.mode == SUPPLIED_CROSS:
            if self.cross_covariance is None:
                raise AttitudeCloneError("supplied-cross mode requires complete C_en")
            c = np.asarray(self.cross_covariance)
            if c.ndim != 2 or np.iscomplexobj(c) or not np.all(np.isfinite(c)):
                raise AttitudeCloneError("finite real two-dimensional C_en required")
            object.__setattr__(self, "cross_covariance", _readonly(c))


@dataclass(frozen=True)
class UpdateRecord:
    measurement_id: str
    padded_current_only: bool
    innovation: np.ndarray
    innovation_covariance: np.ndarray
    gain: np.ndarray
    correlation_mode: str
    noise_source_id: str
    qualification_note: str
    joint_working_noise_psd_checked: bool = field(default=True, init=False)
    physical_calibration_proven: bool = field(default=False, init=False)
    navigation_admission: bool = field(default=False, init=False)

    def __post_init__(self):
        for name in ("innovation", "innovation_covariance", "gain"):
            object.__setattr__(self, name, _readonly(getattr(self, name)))


@dataclass(frozen=True)
class ResetRecord:
    applied_error: np.ndarray
    coordinate_jacobian: np.ndarray
    position_reset_source_id: str
    nominal_state_modified_by_this_module: bool = field(default=False, init=False)
    exact_nonlinear_posterior_claim: bool = field(default=False, init=False)

    def __post_init__(self):
        object.__setattr__(self, "applied_error", _readonly(self.applied_error))
        object.__setattr__(self, "coordinate_jacobian", _readonly(self.coordinate_jacobian))


def augment_attitude_clone(state: ErrorGaussian, clone_jacobian, *, clone_id: str):
    """c=J*x; caller supplies ECEF attitude J=[-K at P,E at PHI].

    Creation is at the current state time; no independent clone prior is added.
    General nonzero means are supported for linear-oracle use. The native
    integration contract should clone after completed full feedback.
    """
    if state.clone_id is not None:
        raise AttitudeCloneError("only one active clone is supported")
    _identity(clone_id, "clone")
    if clone_id in state.used_clone_ids:
        raise AttitudeCloneError("retired clone identity cannot be resurrected")
    j = _array(clone_jacobian, (3, 21), "clone Jacobian")
    if np.linalg.matrix_rank(j) < 3:
        raise AttitudeCloneError("attitude clone Jacobian must have full row rank")
    a = np.vstack((np.eye(21), j))
    return replace(state, mean=a@state.mean, covariance=a@state.covariance@a.T,
                   clone_id=clone_id, clone_time_s=state.current_time_s,
                   used_clone_ids=state.used_clone_ids | {clone_id})


def propagate_current(state: ErrorGaussian, phi_current, process_covariance, *,
                      new_time_s: float, process_noise_independent_of_prior: bool,
                      process_source_id: str, qualification_note: str):
    """Clone remains fixed; Q21 is independent of prior/clone by explicit assumption."""
    if process_noise_independent_of_prior is not True:
        raise AttitudeCloneError("correlated/unknown process noise is unsupported, not silently zeroed")
    _identity(process_source_id, "process source")
    _identity(qualification_note, "process qualification")
    if not math.isfinite(new_time_s) or new_time_s <= state.current_time_s:
        raise AttitudeCloneError("propagation time must strictly increase")
    phi = _array(phi_current, (21, 21), "current Phi")
    q = _psd(process_covariance, 21, "current process covariance")
    full_phi = np.eye(state.dimension)
    full_phi[:21,:21] = phi
    full_q = np.zeros_like(state.covariance)
    full_q[:21,:21] = q
    return replace(state, mean=full_phi@state.mean,
                   covariance=full_phi@state.covariance@full_phi.T+full_q,
                   current_time_s=new_time_s,
                   working_assumptions=_notes(state.working_assumptions,
                       "PROCESS_ZERO_PRIOR_CROSS:"+process_source_id+":"+qualification_note))


def update_measurement(state: ErrorGaussian, dz, H, R, *,
                       correlation: NoiseCorrelation, measurement_id: str,
                       measurement_time_s: float, available_time_s: float):
    """Condition on dz=H*e+n, E[n]=0; innovation=dz-H*mean.

    A current-only H21 is padded, but the clone gain is NOT forced to zero.
    Supplied C_en must cover the full state (24 rows with clone), even for H21.
    Joint-noise PSD and invertible S are required. No NIS/acceptance gate exists.
    """
    _identity(measurement_id, "measurement")
    if measurement_id in state.consumed_measurement_ids:
        raise AttitudeCloneError("measurement identity already consumed")
    if (not math.isfinite(measurement_time_s) or measurement_time_s != state.current_time_s
            or not math.isfinite(available_time_s) or available_time_s < measurement_time_s
            or available_time_s > state.current_time_s):
        raise AttitudeCloneError("measurement must bind current time and already be available; delayed updates unsupported")
    if not isinstance(correlation, NoiseCorrelation):
        raise AttitudeCloneError("explicit NoiseCorrelation contract required")
    if np.iscomplexobj(H):
        raise AttitudeCloneError("measurement H must be real")
    h = np.asarray(H, dtype=float)
    if h.ndim != 2 or h.shape[0] < 1 or not np.all(np.isfinite(h)):
        raise AttitudeCloneError("finite nonempty matrix H required")
    padded = state.dimension == 24 and h.shape[1] == 21
    if padded:
        h = np.column_stack((h,np.zeros((len(h),3))))
    if h.shape[1] != state.dimension:
        raise AttitudeCloneError("H must have current21 or full state column count")
    m = h.shape[0]
    z = _array(dz, (m,), "measurement residual")
    r = _psd(R, m, "measurement noise covariance")
    c = (np.zeros((state.dimension,m)) if correlation.mode == ZERO_CROSS else
         _array(correlation.cross_covariance,(state.dimension,m),"complete state-noise C_en"))
    p = state.covariance
    _psd(np.block([[p,c],[c.T,r]]), state.dimension+m, "joint state-noise covariance")
    s = h@p@h.T+r+h@c+c.T@h.T
    s = .5*(s+s.T)
    try:
        chol = np.linalg.cholesky(s)
        phc = p@h.T+c
        gain = np.linalg.solve(chol.T,np.linalg.solve(chol,phc.T)).T
    except np.linalg.LinAlgError as exc:
        raise AttitudeCloneError("innovation covariance must be positive definite; no loading") from exc
    innovation = z-h@state.mean
    ikh = np.eye(state.dimension)-gain@h
    # e_post=(I-KH)e-Kn. Cross terms have minus signs.
    post = ikh@p@ikh.T+gain@r@gain.T-ikh@c@gain.T-gain@c.T@ikh.T
    updated = replace(state, mean=state.mean+gain@innovation, covariance=post,
                      consumed_measurement_ids=state.consumed_measurement_ids | {measurement_id},
                      working_assumptions=_notes(state.working_assumptions,
                          correlation.mode+":"+correlation.source_id+":"+correlation.qualification_note))
    record = UpdateRecord(measurement_id,padded,innovation,s,gain,correlation.mode,
                          correlation.source_id,correlation.qualification_note)
    return updated, record


def reset_after_full_feedback(state: ErrorGaussian, *, feedback_applied_error,
                              current_position_reset_jacobian, position_reset_source_id: str):
    """Covariance coordinate reset AFTER external full nominal feedback.

    Current P subtracts DRi*dx_P; V subtracts dx_V; rotations left-multiply
    Exp(dx_PHI); bias/scale add their dx. Clone left-multiplies Exp(dx_clone).
    Caller provides DR(BLH_new)*DRi(BLH_old) or a bound fixed-Cartesian I.
    Partial/clipped feedback is unsupported. The module does not change nominal
    poses, and supplying a matrix/source ID is not an independent calibration.
    """
    applied = _array(feedback_applied_error,(state.dimension,),"actual feedback error")
    if not np.array_equal(applied,state.mean):
        raise AttitudeCloneError("full feedback must apply the exact stored mean; clipping unsupported")
    _identity(position_reset_source_id,"position reset source")
    gp = _array(current_position_reset_jacobian,(3,3),"current position reset")
    if np.linalg.matrix_rank(gp) != 3:
        raise AttitudeCloneError("position reset must be an invertible coordinate change")
    g = np.eye(state.dimension)
    g[:3,:3] = gp
    g[6:9,6:9] = left_feedback_reset_jacobian(applied[6:9])
    if state.clone_id is not None:
        g[21:24,21:24] = left_feedback_reset_jacobian(applied[21:24])
    out = replace(state,mean=np.zeros(state.dimension),covariance=g@state.covariance@g.T,
                  working_assumptions=_notes(state.working_assumptions,
                      "LOCAL_FULL_FEEDBACK_RESET:"+position_reset_source_id))
    return out, ResetRecord(applied,g,position_reset_source_id)


def marginalize_clone(state: ErrorGaussian):
    """Discard the clone by marginalization, never by conditioning it to zero."""
    if state.clone_id is None:
        raise AttitudeCloneError("no active clone to marginalize")
    return replace(state,mean=state.mean[:21],covariance=state.covariance[:21,:21],
                   clone_id=None,clone_time_s=None)
