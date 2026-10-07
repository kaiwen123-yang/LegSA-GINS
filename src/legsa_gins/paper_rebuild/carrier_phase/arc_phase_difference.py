"""Unfixed-integer, two-epoch phase contrasts on continuous physical SD arcs.

Input phase is metres, SD is receiver2-receiver1, DD is target-pivot.
No integer values, search, acceptance, raw reader or navigation update occur.
Arc continuity and covariance are supplied qualifications, not inferred truths.
Geometry is evaluated separately at each actual measurement epoch. Fixed-body
baseline, anchor/LOS error, biases and state/measurement correlation remain
working-model assumptions; cancelling integers does not remove these errors.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Sequence
import numpy as np

from .arc_relations import SdArcNode, DdArcRelation
from .multignss import raw, signal_spec


class ArcPhaseDifferenceError(ValueError):
    pass


def _identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ArcPhaseDifferenceError(name + ": explicit identity required")
    return value


def _array(value, shape, name):
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.isfinite(a).all():
        raise ArcPhaseDifferenceError(name + ": finite array of registered shape required")
    return a


def _readonly(value):
    a = np.array(value, copy=True)
    a.setflags(write=False)
    return a


def _psd(value, size, name):
    a = _array(value, (size, size), name)
    if size == 0:
        return _readonly(a)
    tolerance = 128 * np.finfo(float).eps * size * max(
        float(np.max(np.abs(a))), np.finfo(float).tiny)
    if np.max(np.abs(a-a.T)) > tolerance:
        raise ArcPhaseDifferenceError(name + ": nonsymmetric")
    a = (a+a.T)*.5
    if np.linalg.eigvalsh(a)[0] < -tolerance:
        raise ArcPhaseDifferenceError(name + ": not positive semidefinite")
    return _readonly(a)  # No eigenvalue clipping, diagonal loading or inversion.


def _nodes(values):
    values = tuple(values)
    if any(not isinstance(n, SdArcNode) for n in values):
        raise ArcPhaseDifferenceError("physical typed SD nodes required")
    if len(set(values)) != len(values):
        raise ArcPhaseDifferenceError("duplicate physical SD node")
    if len({n.signal for n in values}) != len(values):
        raise ArcPhaseDifferenceError("simultaneous different tokens for one signal")
    return tuple(sorted(values))


def _wavelength(node):
    return signal_spec(raw.SignalIdentity(*(int(x) for x in node.signal.split(":")))).wavelength_m


def _skew(v):
    x,y,z = v
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])


def _rotation(value):
    a = _array(value, (3,3), "body-to-ECEF rotation")
    if not np.allclose(a.T@a, np.eye(3), atol=1e-10, rtol=0.) or abs(np.linalg.det(a)-1)>1e-10:
        raise ArcPhaseDifferenceError("SO(3) required; no normalization")
    return a


@dataclass(frozen=True)
class PhaseEpoch:
    time_s: float
    available_time_s: float | None
    epoch_id: str
    source_id: str
    receiver_pair_id: str
    time_scale_id: str
    phase_convention_id: str
    geometry_source_id: str
    covariance_source_id: str
    relations: tuple[DdArcRelation, ...]
    phase_m: np.ndarray
    geometry_ecef: np.ndarray
    covariance_m2: np.ndarray
    receiver_order: str = "GNSS2_MINUS_GNSS1"
    dd_sign: str = "TARGET_MINUS_PIVOT"
    geometry_frame: str = "ECEF"

    def __post_init__(self):
        if not math.isfinite(self.time_s):
            raise ArcPhaseDifferenceError("finite source time required")
        if self.available_time_s is not None:
            if not math.isfinite(self.available_time_s):
                raise ArcPhaseDifferenceError("finite declared availability required")
            if self.available_time_s < self.time_s:
                raise ArcPhaseDifferenceError("availability precedes measurement")
        # None preserves absent historical arrival/model-ready information.
        # It is allowed only in the geometry-only interface, never silently
        # changed into a current usable measurement by build_phase_difference.
        for name in ("epoch_id","source_id","receiver_pair_id","time_scale_id",
                     "phase_convention_id","geometry_source_id","covariance_source_id"):
            _identity(getattr(self,name),name)
        if (self.receiver_order,self.dd_sign,self.geometry_frame) != (
                "GNSS2_MINUS_GNSS1","TARGET_MINUS_PIVOT","ECEF"):
            raise ArcPhaseDifferenceError("unsupported receiver order, DD sign or frame")
        edges=tuple(self.relations)
        if any(not isinstance(e,DdArcRelation) for e in edges):
            raise ArcPhaseDifferenceError("typed directed DD relations required")
        if len(set(edges)) != len(edges):
            raise ArcPhaseDifferenceError("duplicate directed DD row")
        _nodes(set(n for e in edges for n in (e.target,e.pivot)))
        object.__setattr__(self,"relations",edges)
        m=len(edges)
        object.__setattr__(self,"phase_m",_readonly(_array(self.phase_m,(m,),"phase metres")))
        object.__setattr__(self,"geometry_ecef",_readonly(_array(self.geometry_ecef,(m,3),"geometry")))
        object.__setattr__(self,"covariance_m2",_psd(self.covariance_m2,m,"epoch phase covariance"))
        # Directed rows can form any graph. A deterministic path per canonical
        # relation is used below; extra cycle information is not silently fused.

    @property
    def nodes(self):
        return tuple(sorted(set(n for e in self.relations for n in (e.target,e.pivot))))

    def physical_integer_design(self, nodes: Sequence[SdArcNode]):
        """Coefficient of arbitrary physical SD integers in METRES per cycle."""
        nodes=tuple(nodes)
        if len(set(nodes)) != len(nodes) or not set(self.nodes).issubset(nodes):
            raise ArcPhaseDifferenceError("unique complete physical integer columns required")
        index={node:i for i,node in enumerate(nodes)}
        a=np.zeros((len(self.relations),len(nodes)))
        for row,e in enumerate(self.relations):
            a[row,index[e.target]]=_wavelength(e.target)
            a[row,index[e.pivot]]=-_wavelength(e.pivot)
        return _readonly(a)

    @property
    def fingerprint(self):
        d=hashlib.sha256()
        header={name:getattr(self,name) for name in (
            "time_s","available_time_s","epoch_id","source_id","receiver_pair_id",
            "time_scale_id","phase_convention_id","geometry_source_id",
            "covariance_source_id","receiver_order","dd_sign","geometry_frame")}
        header["relations"]=[e.label for e in self.relations]
        d.update(json.dumps(header,sort_keys=True,separators=(",",":")).encode())
        for a in (self.phase_m,self.geometry_ecef,self.covariance_m2):
            d.update(np.asarray(a,dtype="<f8",order="C").tobytes())
        return d.hexdigest()


@dataclass(frozen=True)
class PhaseArcContinuity:
    start_s: float
    end_s: float
    available_time_s: float | None
    receiver_pair_id: str
    source_id: str
    continuous_nodes: tuple[SdArcNode,...]

    def __post_init__(self):
        if (not all(math.isfinite(x) for x in (self.start_s,self.end_s))
                or self.end_s <= self.start_s):
            raise ArcPhaseDifferenceError("continuous interval required")
        if self.available_time_s is not None and (
                not math.isfinite(self.available_time_s) or self.available_time_s < self.end_s):
            raise ArcPhaseDifferenceError("causal declared continuity availability required")
        _identity(self.receiver_pair_id,"continuity receiver pair")
        _identity(self.source_id,"continuity source")
        object.__setattr__(self,"continuous_nodes",_nodes(self.continuous_nodes))
        # Caller must inspect the ENTIRE interval: equal endpoint tokens alone
        # do not establish that there was no intervening break/retirement.


def _graph(epoch):
    adjacency={n:[] for n in epoch.nodes}
    for column,e in enumerate(epoch.relations):
        adjacency[e.pivot].append((e.target,column,1))
        adjacency[e.target].append((e.pivot,column,-1))
    for n in adjacency:
        adjacency[n].sort(key=lambda x:(x[0],epoch.relations[x[1]].label,x[2]))
    component={}
    for root in sorted(adjacency):
        if root in component: continue
        component[root]=root
        pending=[root]
        while pending:
            n=pending.pop()
            for other,_,_ in adjacency[n]:
                if other not in component:
                    component[other]=root
                    pending.append(other)
    return adjacency,component


def _path(adjacency, relation, width):
    pending=deque([(relation.pivot,np.zeros(width,dtype=np.int64))])
    visited={relation.pivot}
    while pending:
        n,coeff=pending.popleft()
        if n == relation.target: return coeff
        for other,column,sign in adjacency[n]:
            if other not in visited:
                visited.add(other)
                candidate=coeff.copy();candidate[column]+=sign
                pending.append((other,candidate))
    raise ArcPhaseDifferenceError("canonical relation disconnected in an endpoint")


@dataclass(frozen=True)
class PhaseContrastGeometry:
    """Historical observation algebra; not a released navigation measurement.

    Endpoint Q contributions are kept separately. Unknown cross-time covariance
    and missing actual availability do not become zero covariance or zero delay.
    No baseline direction/attitude state or integer value is needed here.
    """
    epoch0: PhaseEpoch
    epoch1: PhaseEpoch
    continuity: PhaseArcContinuity
    relations: tuple[DdArcRelation, ...]
    physical_nodes: tuple[SdArcNode, ...]
    F0: np.ndarray
    F1: np.ndarray
    physical_coefficients_m: np.ndarray
    z_m: np.ndarray
    G0: np.ndarray
    G1: np.ndarray
    epoch0_covariance_contribution_m2: np.ndarray
    epoch1_covariance_contribution_m2: np.ndarray
    declared_available_time_s: float | None
    status: str
    navigation_admitted: bool = field(default=False, init=False)
    joint_covariance_known: bool = field(default=False, init=False)

    @property
    def observation_map(self):
        return _readonly(np.hstack([-self.F0, self.F1]))


@dataclass(frozen=True)
class PhaseDifferenceWorkingBound:
    matrix_m2: np.ndarray
    marginal_bound_source_id: str
    scope: str = "CONDITIONAL_ON_VALID_ENDPOINT_SECOND_MOMENT_UPPER_BOUNDS"
    is_covariance: bool = field(default=False, init=False)
    calibrated: bool = field(default=False, init=False)
    cross_covariance_known: bool = field(default=False, init=False)


def build_phase_contrast_geometry(epoch0: PhaseEpoch, epoch1: PhaseEpoch,
                                  continuity: PhaseArcContinuity):
    """Build a same-arc contrast without inventing time-cross Q or availability."""
    if not isinstance(epoch0, PhaseEpoch) or not isinstance(epoch1, PhaseEpoch) or not isinstance(continuity, PhaseArcContinuity):
        raise ArcPhaseDifferenceError("typed epochs and full-interval continuity required")
    if epoch0.time_s >= epoch1.time_s or epoch0.epoch_id == epoch1.epoch_id:
        raise ArcPhaseDifferenceError("distinct strictly increasing epochs required")
    if (epoch0.receiver_pair_id != epoch1.receiver_pair_id
            or epoch0.time_scale_id != epoch1.time_scale_id
            or epoch0.phase_convention_id != epoch1.phase_convention_id):
        raise ArcPhaseDifferenceError("receiver/time/phase convention mismatch")
    if ((continuity.start_s, continuity.end_s) != (epoch0.time_s, epoch1.time_s)
            or continuity.receiver_pair_id != epoch0.receiver_pair_id):
        raise ArcPhaseDifferenceError("continuity not bound to this interval")
    m0, m1 = len(epoch0.relations), len(epoch1.relations)
    adjacency0,component0=_graph(epoch0);adjacency1,component1=_graph(epoch1)
    common=set(epoch0.nodes)&set(epoch1.nodes)&set(continuity.continuous_nodes)
    components={}
    for n in sorted(common):
        components.setdefault((n.group,component0[n],component1[n]),[]).append(n)
    relations=[]
    for nodes in sorted(components.values(),key=lambda x:x[0]):
        relations.extend(DdArcRelation(n,nodes[0]) for n in nodes[1:])
    relations=tuple(relations)
    f0=np.asarray([_path(adjacency0,e,m0) for e in relations],dtype=np.int64).reshape(len(relations),m0)
    f1=np.asarray([_path(adjacency1,e,m1) for e in relations],dtype=np.int64).reshape(len(relations),m1)
    # Union permits a different/new epoch-only pivot. It must cancel exactly,
    # and no same-SV new token or cross-frequency integer can be inherited.
    physical=tuple(sorted(set(epoch0.nodes)|set(epoch1.nodes)))
    a0=epoch0.physical_integer_design(physical);a1=epoch1.physical_integer_design(physical)
    coefficients0=f0@a0;coefficients1=f1@a1
    expected=np.zeros_like(coefficients0)
    for i,e in enumerate(relations):
        expected[i,physical.index(e.target)]=_wavelength(e.target)
        expected[i,physical.index(e.pivot)]=-_wavelength(e.pivot)
    if not np.array_equal(coefficients0,coefficients1) or not np.array_equal(coefficients0,expected):
        raise ArcPhaseDifferenceError("physical integer coefficients do not cancel exactly")
    declared = (epoch0.available_time_s, epoch1.available_time_s, continuity.available_time_s)
    available = None if any(t is None for t in declared) else float(max(declared))
    return PhaseContrastGeometry(
        epoch0, epoch1, continuity, relations, physical,
        _readonly(f0), _readonly(f1), _readonly(expected),
        _readonly(f1@epoch1.phase_m-f0@epoch0.phase_m),
        _readonly(f0@epoch0.geometry_ecef), _readonly(f1@epoch1.geometry_ecef),
        _psd(f0@epoch0.covariance_m2@f0.T, len(relations), "epoch0 Q contribution"),
        _psd(f1@epoch1.covariance_m2@f1.T, len(relations), "epoch1 Q contribution"),
        available, "UNFIXED_ARC_PHASE_CONTRAST_GEOMETRY" if relations else "NO_CONTINUOUS_RELATIONS")


def unknown_cross_difference_bound(contrast: PhaseContrastGeometry, *,
                                   marginal_bound_source_id: str):
    """Return 2(Q0'+Q1'), an epsilon=1 second-moment upper bound.

    This follows from (x-y)(x-y)^T <= 2xx^T+2yy^T for arbitrary cross moments.
    It is conditional on BOTH supplied endpoint matrices actually bounding
    their error second moments. Raw receiver sigmas do not establish that
    premise. The result is not a covariance, temporal-independence certificate,
    state-measurement bound, or bound on correlations between different factors.
    """
    if not isinstance(contrast, PhaseContrastGeometry):
        raise ArcPhaseDifferenceError("typed geometry-only contrast required")
    _identity(marginal_bound_source_id, "endpoint marginal bound source")
    q = 2*(contrast.epoch0_covariance_contribution_m2
           + contrast.epoch1_covariance_contribution_m2)
    return PhaseDifferenceWorkingBound(
        _psd(q, len(contrast.relations), "conditional unknown-cross bound"),
        marginal_bound_source_id)


@dataclass(frozen=True)
class PhaseAttitudeState:
    time_s: float
    available_time_s: float
    matrix_body_to_ecef: np.ndarray
    body_frame_id: str
    source_id: str

    def __post_init__(self):
        if (not all(math.isfinite(x) for x in (self.time_s,self.available_time_s))
                or self.available_time_s < self.time_s):
            raise ArcPhaseDifferenceError("causal attitude linearization times required")
        _identity(self.body_frame_id,"attitude body frame")
        _identity(self.source_id,"attitude source")
        object.__setattr__(self,"matrix_body_to_ecef",_readonly(_rotation(self.matrix_body_to_ecef)))


@dataclass(frozen=True)
class PhaseDifferenceLinearization:
    prediction_m: np.ndarray
    residual_m: np.ndarray
    prediction_jacobian_ecef_left: np.ndarray
    residual_jacobian_ecef_left: np.ndarray
    rank: int
    nullspace_ecef_left: np.ndarray
    rank_tolerance: float
    attitude_source_ids: tuple[str,str]
    scope: str = "LOCAL_TWO_POSE_LINEARIZATION_NOT_ABSOLUTE_HEADING_OR_INDEPENDENT_SENSOR"


@dataclass(frozen=True)
class ArcPhaseDifferenceFactor:
    epoch0: PhaseEpoch
    epoch1: PhaseEpoch
    continuity: PhaseArcContinuity
    relations: tuple[DdArcRelation,...]
    physical_nodes: tuple[SdArcNode,...]
    F0: np.ndarray
    F1: np.ndarray
    physical_coefficients_m: np.ndarray
    z_m: np.ndarray
    G0: np.ndarray
    G1: np.ndarray
    covariance_m2: np.ndarray
    source_stack_covariance_m2: np.ndarray
    covariance_mode: str
    covariance_source_id: str
    decision_available_time_s: float
    baseline_body_m: np.ndarray
    body_frame_id: str
    baseline_source_id: str
    status: str
    integer_values_used: bool = field(default=False,init=False)
    accepted_integer_measurement: bool = field(default=False,init=False)
    state_measurement_independence_established: bool = field(default=False,init=False)
    covariance_calibrated: bool = field(default=False,init=False)

    @property
    def observation_map(self):
        return _readonly(np.hstack([-self.F0,self.F1]))

    def linearize(self, state0:PhaseAttitudeState, state1:PhaseAttitudeState):
        for e,s in ((self.epoch0,state0),(self.epoch1,state1)):
            if (not isinstance(s,PhaseAttitudeState) or s.time_s != e.time_s
                    or s.available_time_s > self.decision_available_time_s
                    or s.body_frame_id != self.body_frame_id):
                raise ArcPhaseDifferenceError("attitude endpoint/frame/availability mismatch")
        b0=state0.matrix_body_to_ecef@self.baseline_body_m
        b1=state1.matrix_body_to_ecef@self.baseline_body_m
        prediction=self.G1@b1-self.G0@b0
        h=np.hstack([self.G0@_skew(b0),-self.G1@_skew(b1)])
        if len(h):
            _,s,vh=np.linalg.svd(h,full_matrices=True)
            tol=max(h.shape)*np.finfo(float).eps*(float(s[0]) if len(s) else 0.)
            rank=int(np.count_nonzero(s>tol))
            nullspace=vh[rank:].T
        else: rank,tol,nullspace=0,0.,np.eye(6)
        return PhaseDifferenceLinearization(
            _readonly(prediction),_readonly(self.z_m-prediction),
            _readonly(h),_readonly(-h),rank,_readonly(nullspace),float(tol),
            (state0.source_id,state1.source_id))

    def fault_template_m_per_cycle(self,node:SdArcNode,*,endpoint:int):
        """SD node step template; not fault acceptance or receiver localization."""
        if endpoint not in (0,1) or node not in self.physical_nodes:
            raise ArcPhaseDifferenceError("registered physical node and endpoint 0/1 required")
        epoch=self.epoch0 if endpoint==0 else self.epoch1
        a=epoch.physical_integer_design(self.physical_nodes)[:,self.physical_nodes.index(node)]
        return _readonly((-self.F0 if endpoint==0 else self.F1)@a)


def build_phase_difference(epoch0:PhaseEpoch,epoch1:PhaseEpoch,continuity:PhaseArcContinuity,
                           *,covariance_mode:str,covariance_source_id:str,
                           covariance_stack_m2,decision_available_time_s:float,
                           baseline_body_m,body_frame_id:str,baseline_source_id:str):
    """Stateless observation algebra; no endpoint-consumption/admission ledger.

    Callers must prevent double use, or explicitly carry cross-factor covariance.
    WORKING_ZERO_CROSS is an explicit statistical assumption, never a default.
    FULL_STACK uses ordering [all epoch0 phase rows, all epoch1 phase rows].
    """
    if not isinstance(epoch0,PhaseEpoch) or not isinstance(epoch1,PhaseEpoch) or not isinstance(continuity,PhaseArcContinuity):
        raise ArcPhaseDifferenceError("typed epochs and full-interval continuity required")
    if epoch0.time_s>=epoch1.time_s or epoch0.epoch_id==epoch1.epoch_id:
        raise ArcPhaseDifferenceError("distinct strictly increasing epochs required")
    if (epoch0.receiver_pair_id!=epoch1.receiver_pair_id
            or epoch0.time_scale_id!=epoch1.time_scale_id
            or epoch0.phase_convention_id!=epoch1.phase_convention_id):
        raise ArcPhaseDifferenceError("receiver/time/phase convention mismatch")
    if ((continuity.start_s,continuity.end_s)!=(epoch0.time_s,epoch1.time_s)
            or continuity.receiver_pair_id!=epoch0.receiver_pair_id):
        raise ArcPhaseDifferenceError("continuity not bound to this interval")
    if any(t is None for t in (epoch0.available_time_s, epoch1.available_time_s,
                               continuity.available_time_s)):
        raise ArcPhaseDifferenceError("actual source availability unknown; geometry-only interface required")
    if (not math.isfinite(decision_available_time_s)
            or decision_available_time_s<max(epoch0.available_time_s,epoch1.available_time_s,continuity.available_time_s)):
        raise ArcPhaseDifferenceError("decision precedes actual source availability")
    _identity(covariance_source_id,"joint covariance source")
    _identity(body_frame_id,"baseline body frame")
    _identity(baseline_source_id,"fixed body baseline source")
    r=_array(baseline_body_m,(3,),"body baseline metres")
    if np.linalg.norm(r)<=0:
        raise ArcPhaseDifferenceError("nonzero explicitly supplied body baseline required")
    m0,m1=len(epoch0.relations),len(epoch1.relations)
    if covariance_mode=="WORKING_ZERO_CROSS":
        if covariance_stack_m2 is not None:
            raise ArcPhaseDifferenceError("zero-cross mode must not override supplied covariance")
        q=np.zeros((m0+m1,m0+m1))
        q[:m0,:m0]=epoch0.covariance_m2;q[m0:,m0:]=epoch1.covariance_m2
    elif covariance_mode=="FULL_STACK":
        if covariance_stack_m2 is None:
            raise ArcPhaseDifferenceError("full cross-time covariance missing")
        q=_psd(covariance_stack_m2,m0+m1,"joint source covariance")
        if not np.array_equal(q[:m0,:m0],epoch0.covariance_m2) or not np.array_equal(q[m0:,m0:],epoch1.covariance_m2):
            raise ArcPhaseDifferenceError("joint covariance marginals do not match endpoints")
    else:
        raise ArcPhaseDifferenceError("explicit FULL_STACK or WORKING_ZERO_CROSS required")
    q=_psd(q,m0+m1,"joint source covariance")
    contrast = build_phase_contrast_geometry(epoch0, epoch1, continuity)
    relations, physical = contrast.relations, contrast.physical_nodes
    f0, f1 = contrast.F0, contrast.F1
    expected = contrast.physical_coefficients_m
    d = contrast.observation_map
    return ArcPhaseDifferenceFactor(
        epoch0,epoch1,continuity,relations,physical,_readonly(f0),_readonly(f1),
        _readonly(expected),_readonly(f1@epoch1.phase_m-f0@epoch0.phase_m),
        _readonly(f0@epoch0.geometry_ecef),_readonly(f1@epoch1.geometry_ecef),
        _psd(d@q@d.T,len(relations),"difference covariance"),q,covariance_mode,
        covariance_source_id,float(decision_available_time_s),_readonly(r),
        body_frame_id,baseline_source_id,
        "UNFIXED_ARC_PHASE_DIFFERENCE" if relations else "NO_CONTINUOUS_RELATIONS")


def difference_cross_covariance(first:ArcPhaseDifferenceFactor,second:ArcPhaseDifferenceFactor,
                                *,source_cross_covariance_m2,source_id:str):
    """Explicit covariance between contrasts, including shared endpoint noise.

    Cross array rows/columns follow each factor's [epoch0 rows,epoch1 rows].
    Marginals + cross must form a PSD matrix. A repeated identical epoch must
    have its full self covariance in the corresponding cross block.
    Return is NOT an independence or state/measurement-correlation certificate.
    """
    _identity(source_id,"cross-factor covariance source")
    n0=len(first.source_stack_covariance_m2);n1=len(second.source_stack_covariance_m2)
    c=_array(source_cross_covariance_m2,(n0,n1),"cross-factor source covariance")
    left=(first.epoch0,first.epoch1);right=(second.epoch0,second.epoch1)
    lo=0
    for a in left:
        hi=0
        for b in right:
            if a.epoch_id==b.epoch_id:
                if a.fingerprint!=b.fingerprint:
                    raise ArcPhaseDifferenceError("same epoch identity has different payload")
                if not np.array_equal(c[lo:lo+len(a.relations),hi:hi+len(b.relations)],a.covariance_m2):
                    raise ArcPhaseDifferenceError("shared endpoint covariance was erased")
            hi+=len(b.relations)
        lo+=len(a.relations)
    _psd(np.block([[first.source_stack_covariance_m2,c],
                   [c.T,second.source_stack_covariance_m2]]),n0+n1,"joint two-factor sources")
    return _readonly(first.observation_map@c@second.observation_map.T)
