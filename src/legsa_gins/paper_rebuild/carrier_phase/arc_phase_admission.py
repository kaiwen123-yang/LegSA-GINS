"""Conditional local consistency and shadow lifecycle for unfixed phase contrasts.

No truth labels, integer search, physical noise defaults, real-data reader or
navigation update. Every probability statement is conditional on the frozen
information set and supplied error-second-moment/remainder qualifications.
A passing gate does not prove fault absence or trusted heading.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
import hashlib
import json
import math
import numpy as np

from .arc_phase_difference import (
    PhaseContrastGeometry, PhaseAttitudeState, _array, _identity,
    _readonly, _skew,
)
from .arc_relations import SdArcNode


class PhaseAdmissionError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise PhaseAdmissionError(message)



def _psd(value, size, name):
    """Validate by diagonal congruence, preserving tiny physical modes.

    Unlike a global matrix-scale cutoff, this cannot hide a negative low-scale
    variance/cross block behind a large state variance. No clipping or loading.
    Half-before-add also avoids overflow while symmetrizing finite entries.
    """
    a=_array(value,(size,size),name)
    if size==0:
        return _readonly(a)
    diagonal=np.diag(a)
    _require(np.all(diagonal>=0),name+": negative diagonal")
    zero=diagonal==0
    _require(not np.any(a[zero,:]!=0) and not np.any(a[:,zero]!=0),
             name+": zero variance has nonzero cross moment")
    positive=~zero
    if not positive.any():
        return _readonly(a)
    scales=np.sqrt(diagonal[positive])
    try:
        with np.errstate(over="raise",invalid="raise",divide="raise"):
            normalized=(a[np.ix_(positive,positive)]/scales[:,None])/scales[None,:]
    except FloatingPointError as exc:
        raise PhaseAdmissionError(name+": nonfinite scaled PSD validation") from exc
    _require(np.isfinite(normalized).all(),name+": nonfinite scaled matrix")
    tolerance=128*np.finfo(float).eps*size*max(1.,float(np.max(abs(normalized))))
    _require(np.max(abs(normalized-normalized.T))<=tolerance,name+": nonsymmetric")
    normalized=normalized*.5+normalized.T*.5
    _require(np.linalg.eigvalsh(normalized)[0]>=-tolerance,
             name+": not positive semidefinite")
    return _readonly(a*.5+a.T*.5)

def _finite_time(value, name):
    _require(math.isfinite(value), name+": finite time required")


def _available(value, name):
    if value is not None:
        _finite_time(value, name)


@dataclass(frozen=True)
class AdmissionSpecification:
    baseline_body_m: np.ndarray
    body_frame_id: str
    baseline_source_id: str
    alpha_prior: float
    alpha_projected: float
    remainder_bound_m: float
    remainder_source_id: str
    remainder_domain_source_id: str
    remainder_domain_qualified: bool
    qualification_scope: str
    conditioning_information_set_id: str
    frozen_at_s: float
    available_time_s: float | None

    def __post_init__(self):
        object.__setattr__(self, "baseline_body_m",
                           _readonly(_array(self.baseline_body_m, (3,), "body baseline")))
        _require(np.linalg.norm(self.baseline_body_m)>0, "nonzero baseline required")
        for key in ("body_frame_id", "baseline_source_id", "remainder_source_id",
                    "remainder_domain_source_id", "qualification_scope",
                    "conditioning_information_set_id"):
            _identity(getattr(self, key), key)
        _finite_time(self.frozen_at_s, "specification freeze")
        _available(self.available_time_s, "specification availability")
        _require(type(self.remainder_domain_qualified) is bool, "explicit remainder qualification")
        _require(all(math.isfinite(a) and a>0 for a in
                     (self.alpha_prior, self.alpha_projected))
                 and self.alpha_prior+self.alpha_projected<1, "explicit alpha allocation")
        _require(math.isfinite(self.remainder_bound_m) and self.remainder_bound_m>=0,
                 "explicit finite nonnegative remainder bound")


@dataclass(frozen=True)
class ConditionalErrorBounds:
    """All moments refer to the SAME frozen conditioning information set I.

    P_cov >= Cov(delta|I), mean_outer >= E[delta|I] E[delta|I]^T,
    M >= E[e e^T|I]. C is the declared cross SECOND MOMENT, including
    mean terms. PSD of K is algebraic validation, not physical certification.
    """
    state_covariance_rad2: np.ndarray
    state_mean_outer_bound_rad2: np.ndarray
    phase_second_moment_bound_m2: np.ndarray
    cross_mode: str
    cross_second_moment_rad_m: np.ndarray | None
    state_source_id: str
    mean_bound_source_id: str
    phase_bound_source_id: str
    cross_source_id: str
    conditioning_information_set_id: str
    frozen_at_s: float
    available_time_s: float | None
    qualified: bool
    qualification_scope: str

    def __post_init__(self):
        pc = _psd(self.state_covariance_rad2, 6, "joint two-state covariance")
        pb = _psd(self.state_mean_outer_bound_rad2, 6, "state mean outer bound")
        m = np.asarray(self.phase_second_moment_bound_m2, dtype=float)
        _require(m.ndim==2 and m.shape[0]==m.shape[1], "phase moment square matrix")
        m = _psd(m, len(m), "phase error second-moment bound")
        object.__setattr__(self, "state_covariance_rad2", pc)
        object.__setattr__(self, "state_mean_outer_bound_rad2", pb)
        object.__setattr__(self, "phase_second_moment_bound_m2", m)
        for name in ("state_source_id", "mean_bound_source_id", "phase_bound_source_id",
                     "cross_source_id", "conditioning_information_set_id", "qualification_scope"):
            _identity(getattr(self, name), name)
        _finite_time(self.frozen_at_s, "bound freeze")
        _available(self.available_time_s, "bound availability")
        _require(type(self.qualified) is bool, "explicit conditional moment qualification")
        if self.cross_mode=="FULL_DECLARED_CROSS":
            c = _array(self.cross_second_moment_rad_m, (6, len(m)), "cross second moment")
            _psd(np.block([[pc+pb,c],[c.T,m]]), 6+len(m), "declared joint second-moment bound")
            object.__setattr__(self, "cross_second_moment_rad_m", _readonly(c))
        elif self.cross_mode=="UNKNOWN_CROSS_BOUND":
            _require(self.cross_second_moment_rad_m is None,
                     "unknown cross must not supply an implicit zero cross")
        else:
            raise PhaseAdmissionError("explicit supported cross mode required")

    @property
    def state_second_moment_bound(self):
        return _readonly(self.state_covariance_rad2+self.state_mean_outer_bound_rad2)


@dataclass(frozen=True)
class ConsistencyStatistic:
    dimension: int
    statistic: float
    threshold: float
    whitened_norm: float
    conservative_whitened_remainder_radius: float
    minimum_eigenvalue: float
    maximum_eigenvalue: float
    solve_relative_residual: float
    rejects: bool
    interpretation: str = "CONDITIONAL_MARKOV_MODEL_REJECTION_NOT_FALSE_ACCEPTANCE"


@dataclass(frozen=True)
class FaultProjection:
    node: SdArcNode
    endpoint: int
    template_m_per_cycle: np.ndarray
    projected_template_m_per_cycle: np.ndarray
    relative_projected_norm: float
    locally_absorbable_to_numerical_tolerance: bool


@dataclass(frozen=True)
class PhaseAdmissionDecision:
    assessment_id: str
    status: str
    reasons: tuple[str, ...]
    conditionally_usable: bool
    endpoints_consumed: bool
    prior: ConsistencyStatistic | None = None
    projected: ConsistencyStatistic | None = None
    residual_m: np.ndarray | None = None
    prediction_jacobian: np.ndarray | None = None
    innovation_second_moment_bound_m2: np.ndarray | None = None
    nuisance_rank: int | None = None
    nuisance_residual_dimension: int | None = None
    projection_leakage_norm: float | None = None
    projected_basis: np.ndarray | None = None
    state_nullspace: np.ndarray | None = None
    fault_projections: tuple[FaultProjection, ...] = ()
    conditioning_information_set_id: str | None = None
    alpha_model_rejection_bound: float | None = None
    actual_available_time_s: float | None = None
    joint_covariance_known: bool = False
    navigation_admitted: bool = False
    phase_fault_proven: bool = False
    fault_false_acceptance_probability: None = None
    direction_point_ecef: None = None
    between_factor_independence_established: bool = False


def innovation_bound(j, bounds):
    """Bound E[(J delta+e)(...)^T | I], not an inferred actual covariance."""
    j = _array(j, (len(bounds.phase_second_moment_bound_m2), 6), "attitude Jacobian")
    p, m = bounds.state_second_moment_bound, bounds.phase_second_moment_bound_m2
    if bounds.cross_mode=="FULL_DECLARED_CROSS":
        c = bounds.cross_second_moment_rad_m
        s = j@p@j.T+m+j@c+c.T@j.T
    else:
        s = 2*(j@p@j.T+m)
    return _psd(s, len(m), "innovation second-moment bound")


def consistency_statistic(residual, moment_bound, *, epsilon_m, alpha):
    """Return (statistic, unresolved reason); no clipping/floor/pseudoinverse.

    E[w w^T|I]<=S and ||eta||<=epsilon imply
    P(max(0,||S^-1/2 r||-epsilon/sqrt(lambda_min(S)))^2 > m/alpha | I)
    <= alpha, provided S is reliably positive definite.
    """
    r = np.asarray(residual, dtype=float)
    _require(r.ndim==1 and np.isfinite(r).all(), "finite residual vector")
    s = _psd(moment_bound, len(r), "gate second-moment bound")
    _require(math.isfinite(epsilon_m) and epsilon_m>=0, "finite remainder")
    _require(math.isfinite(alpha) and 0<alpha<1, "explicit gate alpha")
    if not len(r):
        return None, "EMPTY_RESIDUAL_SUPPORT"
    eigen = np.linalg.eigvalsh(s)
    # A tiny mode is NOT deleted to pass: the entire assessment is unresolved.
    numerical_floor = 64*np.finfo(float).eps*len(r)*max(float(eigen[-1]),np.finfo(float).tiny)
    if eigen[0] <= numerical_floor:
        return None, "UNRELIABLE_POSITIVE_DEFINITE_SUPPORT"
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            chol = np.linalg.cholesky(s)
            white = np.linalg.solve(chol, r)
            solution = np.linalg.solve(chol.T, white)
            denominator = np.linalg.norm(s)*np.linalg.norm(solution)+np.linalg.norm(r)
            error = float(np.linalg.norm(s@solution-r)/(denominator or 1.))
            if not math.isfinite(error) or error > 512*np.finfo(float).eps*len(r):
                return None, "LINEAR_SOLVE_RESIDUAL_FAILED"
            v = float(np.linalg.norm(white))
            radius = float(epsilon_m/np.sqrt(eigen[0]))
            t = max(0., v-radius)**2
            threshold = len(r)/alpha
            if not all(math.isfinite(x) for x in (v,radius,t,threshold)):
                return None, "NONFINITE_STATISTIC"
    except (np.linalg.LinAlgError, FloatingPointError):
        return None, "NUMERICAL_SOLVE_FAILED"
    return ConsistencyStatistic(len(r),t,threshold,v,radius,float(eigen[0]),
                                float(eigen[-1]),error,t>threshold), None


def canonical_endpoint_key(epoch):
    # Caller still owns authoritative timing/source lineage. Changing IDs or
    # DD pivot does not allocate a fresh copy of the same physical epoch.
    return (epoch.receiver_pair_id, epoch.time_scale_id, float(epoch.time_s),
            epoch.phase_convention_id)


def _jsonable(x):
    if isinstance(x, np.ndarray):
        return {"dtype":str(x.dtype),"shape":x.shape,"values":x.tolist()}
    if is_dataclass(x):
        return {f.name:_jsonable(getattr(x,f.name)) for f in fields(x)}
    if isinstance(x, (tuple,list)):
        return [_jsonable(v) for v in x]
    if isinstance(x, dict):
        return {k:_jsonable(v) for k,v in x.items()}
    if isinstance(x, np.generic):
        return x.item()
    return x


def _digest(x):
    return hashlib.sha256(json.dumps(_jsonable(x),sort_keys=True,
                                    separators=(",",":")).encode()).hexdigest()


@dataclass(frozen=True)
class RevocationNotice:
    event_id: str
    revoked_assessment_ids: tuple[str, ...]
    source_id: str
    notice_time_s: float
    external_filter_rollback_confirmed: bool = False


class PhaseAdmissionLedger:
    """In-memory single-ledger shadow consumption, never a navigation rollback.

    A statistical attempt permanently consumes both canonical epochs, regardless
    of its result. Retirement/invalidation does not refund those observations.
    Unknown qualifications do not inspect residuals and do not consume epochs.
    Persistence and preventing external bypass require an upper-layer owner.
    """
    def __init__(self, ledger_id):
        _identity(ledger_id, "ledger identity")
        self.ledger_id = ledger_id
        self._consumed = {}
        self._records = {}
        self._events = {}
        self._retired = {}
        self._last_action_time = -math.inf

    @property
    def consumed_endpoint_count(self):
        return len(self._consumed)

    @property
    def active_assessment_ids(self):
        return tuple(sorted(k for k,v in self._records.items() if v["state"]=="ACTIVE"))

    def state(self, assessment_id):
        return self._records[assessment_id]["state"]

    def _prior_result(self, assessment_id, digest):
        if assessment_id not in self._records:
            return None
        record = self._records[assessment_id]
        _require(record["digest"]==digest, "assessment identity rebound to different inputs")
        if record["state"]=="REVOKED":
            return replace(record["decision"],status="REJECTED",
                           reasons=("PREVIOUSLY_REVOKED",),conditionally_usable=False)
        return record["decision"]

    def _reserve(self, assessment_id, digest, g, decision_time):
        _require(assessment_id not in self._records, "assessment already exists")
        if decision_time<self._last_action_time:
            return "OUT_OF_ORDER_DECISION"
        keys = tuple(canonical_endpoint_key(e) for e in (g.epoch0,g.epoch1))
        if any(k in self._consumed for k in keys):
            return "ENDPOINT_ALREADY_CONSUMED"
        dependencies = tuple(node for k,node in enumerate(g.physical_nodes)
                             if np.any(g.physical_coefficients_m[:,k] != 0))
        for node in dependencies:
            retirement = self._retired.get((g.epoch0.receiver_pair_id,node))
            if retirement is not None and g.epoch1.time_s>=retirement:
                return "RETIRED_PHYSICAL_TOKEN"
        for key in keys:
            self._consumed[key] = assessment_id
        self._records[assessment_id] = dict(digest=digest,state="RESERVED",decision=None,
             keys=keys,start=g.epoch0.time_s,end=g.epoch1.time_s,
             pair=g.epoch0.receiver_pair_id,nodes=dependencies)
        self._last_action_time=decision_time
        return None

    def _finish(self, decision):
        record=self._records[decision.assessment_id]
        record["decision"]=decision
        record["state"]="ACTIVE" if decision.conditionally_usable else "CONSUMED"

    def invalidate(self, *, event_id, receiver_pair_id, node, interval_start_s,
                   interval_end_s, notice_time_s, source_id, retire_from_s=None):
        """Explicit source evidence, NOT automatically generated from fault truth.

        The invalidation interval and retirement time are separate declarations.
        Retirement invalidates use of this token at/after retire_from_s, including
        an already active interval ending after that time even when the explicit
        invalidation interval is later. Earlier completed factors stay active.
        """
        for value,name in ((event_id,"event"),(receiver_pair_id,"receiver pair"),(source_id,"source")):
            _identity(value,name)
        _require(isinstance(node,SdArcNode),"typed physical node")
        for value in (interval_start_s,interval_end_s,notice_time_s):
            _finite_time(value,"event time")
        _require(interval_start_s<=interval_end_s<=notice_time_s,"causal closed invalidation interval")
        if retire_from_s is not None:
            _finite_time(retire_from_s,"retirement time")
            _require(retire_from_s<=notice_time_s,"future retirement evidence")
        digest=_digest((receiver_pair_id,node,interval_start_s,interval_end_s,
                        notice_time_s,source_id,retire_from_s))
        if event_id in self._events:
            old_digest,notice=self._events[event_id]
            _require(old_digest==digest,"event identity rebound")
            return notice
        _require(notice_time_s>=self._last_action_time,"out-of-order source event")
        revoked=[]
        for name,record in self._records.items():
            if (record["state"]=="ACTIVE" and record["pair"]==receiver_pair_id
                    and node in record["nodes"]
                    and (max(record["start"],interval_start_s)<=min(record["end"],interval_end_s)
                         or (retire_from_s is not None and record["end"]>=retire_from_s))):
                record["state"]="REVOKED";revoked.append(name)
        if retire_from_s is not None:
            key=(receiver_pair_id,node)
            self._retired[key]=min(retire_from_s,self._retired.get(key,math.inf))
        self._last_action_time=notice_time_s
        notice=RevocationNotice(event_id,tuple(sorted(revoked)),source_id,notice_time_s)
        self._events[event_id]=(digest,notice)
        return notice


def assess_phase_contrast(g, state0, state1, specification, bounds, *,
                          ledger, assessment_id, decision_time_s):
    """One frozen, truth-blind local assessment and conservative epoch reservation."""
    _require(isinstance(g,PhaseContrastGeometry),"typed contrast geometry")
    _require(isinstance(specification,AdmissionSpecification),"typed frozen specification")
    _require(isinstance(bounds,ConditionalErrorBounds),"typed conditional bounds")
    _require(isinstance(ledger,PhaseAdmissionLedger),"single owner ledger required")
    _identity(assessment_id,"assessment identity")
    _finite_time(decision_time_s,"decision")
    spec=specification
    _require(bounds.phase_second_moment_bound_m2.shape==(len(g.relations),len(g.relations)),
             "phase bound must match contrast support")
    _require(bounds.conditioning_information_set_id==spec.conditioning_information_set_id
             and bounds.frozen_at_s==spec.frozen_at_s,"same frozen conditioning information set required")
    _require(spec.frozen_at_s<=decision_time_s,"configuration frozen after decision")
    _require(bounds.qualification_scope==spec.qualification_scope,
             "state/source/remainder qualification scopes must agree")
    for epoch,state in ((g.epoch0,state0),(g.epoch1,state1)):
        _require(isinstance(state,PhaseAttitudeState) and state.time_s==epoch.time_s
                 and state.body_frame_id==spec.body_frame_id,"two-pose time/frame identity")
    digest=_digest((g,state0,state1,spec,bounds,decision_time_s))
    old=ledger._prior_result(assessment_id,digest)
    if old is not None:
        return old
    def result(status,reasons,consumed=False,**kwargs):
        return PhaseAdmissionDecision(assessment_id,status,tuple(reasons),
            status=="CONDITIONALLY_USABLE",consumed,
            conditioning_information_set_id=spec.conditioning_information_set_id,**kwargs)
    availability=(g.declared_available_time_s,state0.available_time_s,state1.available_time_s,
                  spec.available_time_s,bounds.available_time_s)
    unknown=[]
    if any(t is None for t in availability):
        unknown.append("ACTUAL_AVAILABILITY_UNKNOWN")
    elif max(availability)>decision_time_s:
        unknown.append("NOT_YET_AVAILABLE")
    if (state0.available_time_s>spec.frozen_at_s
            or state1.available_time_s>spec.frozen_at_s):
        unknown.append("FROZEN_STATE_NOT_AVAILABLE")
    # The current contrast API combines arrival and geometry/support readiness.
    # Conservatively require all of it by freeze; this does not certify that a
    # caller did not inspect residuals before declaring the conditioning set.
    if g.declared_available_time_s is not None and g.declared_available_time_s>spec.frozen_at_s:
        unknown.append("FROZEN_GEOMETRY_SUPPORT_NOT_AVAILABLE")
    if not bounds.qualified:
        unknown.append("CONDITIONAL_ERROR_MOMENT_BOUND_UNQUALIFIED")
    if not spec.remainder_domain_qualified:
        unknown.append("REMAINDER_DOMAIN_NOT_QUALIFIED")
    if (spec.available_time_s is not None and spec.available_time_s>spec.frozen_at_s
            or bounds.available_time_s is not None and bounds.available_time_s>spec.frozen_at_s):
        unknown.append("BOUND_OR_SPEC_NOT_AVAILABLE_AT_FREEZE")
    if unknown:
        return result("UNKNOWN",unknown)
    refusal=ledger._reserve(assessment_id,digest,g,decision_time_s)
    if refusal:
        return result("REJECTED",(refusal,))
    available=float(max(availability))
    try:
        with np.errstate(over="raise",invalid="raise",divide="raise"):
            decision=_assess_reserved(g,state0,state1,spec,bounds,available,result)
    except (ValueError,np.linalg.LinAlgError,FloatingPointError,OverflowError) as exc:
        # A reserved attempt stays consumed. Arithmetic failure cannot turn into
        # zero normalized residual, a passing gate, or refunded phase endpoints.
        decision=result("UNRESOLVED",
            ("NUMERICAL_ASSESSMENT_FAILED:"+type(exc).__name__,),True,
            actual_available_time_s=available)
    ledger._finish(decision)
    return decision


def _assess_reserved(g,state0,state1,spec,bounds,available,result):
    b0=state0.matrix_body_to_ecef@spec.baseline_body_m
    b1=state1.matrix_body_to_ecef@spec.baseline_body_m
    prediction=g.G1@b1-g.G0@b0
    residual=g.z_m-prediction
    j=np.hstack([g.G0@_skew(b0),-g.G1@_skew(b1)])
    u,singular,vh=np.linalg.svd(j,full_matrices=True)
    tolerance=max(j.shape)*np.finfo(float).eps*(float(singular[0]) if len(singular) else 0.)
    rank=int(np.count_nonzero(singular>tolerance))
    left=u[:,rank:]
    s=innovation_bound(j,bounds)
    prior,prior_problem=consistency_statistic(residual,s,epsilon_m=spec.remainder_bound_m,
                                            alpha=spec.alpha_prior)
    projected,projected_problem=consistency_statistic(left.T@residual,left.T@s@left,
        epsilon_m=spec.remainder_bound_m,alpha=spec.alpha_projected)
    faults=[]
    for endpoint,epoch,f in ((0,g.epoch0,-g.F0),(1,g.epoch1,g.F1)):
        design=epoch.physical_integer_design(g.physical_nodes)
        for col,node in enumerate(g.physical_nodes):
            template=f@design[:,col]
            projected_template=left.T@template
            size=float(np.linalg.norm(template))
            psize=float(np.linalg.norm(projected_template))
            ratio=psize/size if size else 0.
            absorbable=psize<=128*np.finfo(float).eps*max(1,len(template))*max(size,np.finfo(float).tiny)
            faults.append(FaultProjection(node,endpoint,_readonly(template),
                           _readonly(projected_template),ratio,absorbable))
    rejection=[]
    if prior is not None and prior.rejects:
        rejection.append("PRIOR_ASSISTED_MODEL_INCONSISTENT")
    if projected is not None and projected.rejects:
        rejection.append("PROJECTED_MODEL_INCONSISTENT")
    if rejection:
        status,reasons="REJECTED",rejection
    elif len(left.T)==0:
        status,reasons="UNRESOLVED",["NO_NUISANCE_RESIDUAL_REDUNDANCY"]
    elif prior_problem or projected_problem:
        status,reasons="UNRESOLVED",[x for x in (prior_problem,projected_problem) if x]
    else:
        status,reasons="CONDITIONALLY_USABLE",["DECLARED_MODEL_NOT_REJECTED_FAULT_ABSENCE_UNPROVEN"]
    decision=result(status,reasons,True,prior=prior,projected=projected,
        residual_m=_readonly(residual),prediction_jacobian=_readonly(j),
        innovation_second_moment_bound_m2=s,nuisance_rank=rank,
        nuisance_residual_dimension=left.shape[1],
        projection_leakage_norm=float(np.linalg.norm(left.T@j)),
        projected_basis=_readonly(left),state_nullspace=_readonly(vh[rank:].T),
        fault_projections=tuple(faults),
        alpha_model_rejection_bound=spec.alpha_prior+spec.alpha_projected,
        actual_available_time_s=available)
    return decision
