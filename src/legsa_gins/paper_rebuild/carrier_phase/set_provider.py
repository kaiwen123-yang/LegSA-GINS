"""Conditional complete-source-set validation and offline current-epoch provider.

No integer search, no old top-two AdmissionDecision, no physical FIX claim.
The owner wraps lifecycle once per slot. Only a five-slot common-origin streak
with a feasible same-cost sphere point may yield a research baseline. Timing is
explicit offline event replay; processing wall time is reported independently.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass,field
import hashlib,json,math,time
import numpy as np
from .candidate_lifecycle import CompleteSourceSet,ConditionalCandidateSet,LifecycleConfig,LifecycleCalls,CurrentSetDomain
from .candidate_envelope import CircularArc
from .sphere_cap_envelope import sphere_direction_envelope,cover_from_arcs,SphereDirectionEnvelope
from .arc_projection import transport_epoch
from .measurement import CarrierBaselineMeasurement
from .temporal import TemporalModelError,model_fingerprint,positive_definite
from ..horizontal_literature.ext01_clambda import constrained_baseline


@dataclass(frozen=True)
class SetProviderPolicy:
    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)
    validation_epochs: int = 5
    max_source_age_s: float = 10.
    max_source_candidates: int = 64
    angular_floor_rad: float = math.radians(1.5)

    def __post_init__(self):
        if (self.validation_epochs!=5 or not math.isfinite(self.max_source_age_s)
                or self.max_source_age_s<=self.lifecycle.epoch_interval_s*5
                or type(self.max_source_candidates) is not int or self.max_source_candidates<1
                or not math.isfinite(self.angular_floor_rad) or not 0<self.angular_floor_rad<math.pi/2):
            raise TemporalModelError('invalid registered set-provider policy')


@dataclass
class SetProviderCalls:
    lifecycle: LifecycleCalls = field(default_factory=LifecycleCalls)
    geometry_limit: int = 115
    sphere_limit: int = 60
    geometry_calls: int = 0
    python_sphere_calls: int = 0

    def consume(self,kind):
        fieldname,limit=('geometry_calls',self.geometry_limit) if kind=='geometry' else ('python_sphere_calls',self.sphere_limit)
        if type(limit) is not int or limit<0 or getattr(self,fieldname)>=limit:
            raise TemporalModelError('set-provider '+kind+' call budget exhausted')
        setattr(self,fieldname,getattr(self,fieldname)+1)


@dataclass(frozen=True)
class SetValidationEpoch:
    time_s: float
    original_model_fingerprint: str
    transformed_model_fingerprint: str
    domain_fingerprint: str
    class_origins: tuple[str,...]
    integer_items: tuple[tuple[str,int],...]
    sphere_raw_cost: float
    expanded_raw_threshold: float
    sphere_cost_identity_error: float


@dataclass(frozen=True)
class SetValidationReceipt:
    source_fingerprint: str
    source_selected_at_s: float
    source_available_at_s: float
    registered_length_m: float
    epochs: tuple[SetValidationEpoch,...]
    common_origin_fingerprints: tuple[str,...]
    logical_decision_time_s: float
    time_semantics: str = 'OFFLINE_OBSERVATION_EVENT_REPLAY_WITH_RECORDED_ACQUISITION_AVAILABILITY'
    all_global_current_alternatives_covered: bool = False
    accepted_true_integer: bool = False
    false_fix_probability: None = None


@dataclass(frozen=True)
class SetProviderStep:
    status: str
    domain: CurrentSetDomain | None
    geometry: tuple[SphereDirectionEnvelope | None,...]
    geometry_errors: tuple[str,...]
    receipt: SetValidationReceipt | None
    measurement: CarrierBaselineMeasurement
    validation_streak: int
    processing_wall_s: float
    scope: str = 'RESEARCH_POINT_CONDITIONAL_ON_COMPLETE_ORIGINAL_SOURCE_AND_WORKING_MODEL'


def _plain(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:_plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [_plain(v) for v in value]
    return value


def _domain_fingerprint(domain):
    return hashlib.sha256(json.dumps(_plain(asdict(domain)),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class CompleteSetPointProvider:
    def __init__(self,source:CompleteSourceSet,*,source_available_at_s:float,
                 policy:SetProviderPolicy=SetProviderPolicy()):
        if (not isinstance(source,CompleteSourceSet) or not math.isfinite(source_available_at_s)
                or source_available_at_s<source.selected_at):
            raise TemporalModelError('source and separately recorded causal availability required')
        if len(source.integers)>policy.max_source_candidates:
            raise TemporalModelError('complete source exceeds activation resource cap; never truncate integers')
        self.source=source;self.source_available_at_s=float(source_available_at_s);self.policy=policy
        self.lifecycle=ConditionalCandidateSet(source,policy.lifecycle)
        self._history=[];self._ended=False

    @property
    def alive_nodes(self):return self.lifecycle.alive_nodes

    @property
    def terminal(self):return self._ended or self.lifecycle.physically_ended

    def advance(self,model,*,time_s,qualified_nodes,horizontal_axes,decision_time_s,calls:SetProviderCalls):
        """Consume exactly one chronological slot; catchup history never exports.

        decision_time_s is a declared logical event time, not a claim of actual
        zero runtime. If it instead includes current processing latency and thus
        differs from model.time_s, this method intentionally does not export.
        The scheduler must separately record full acquisition service time when
        constructing source_available_at_s; this method never edits selected_at.
        """
        started=time.monotonic();t=float(time_s);decision=float(decision_time_s)
        if (not math.isfinite(t) or not math.isfinite(decision) or decision<t
                or decision<self.source_available_at_s):
            raise TemporalModelError('decision precedes current data or recorded source availability')
        if model is not None and float(model.time_s)!=t:
            raise TemporalModelError('current model/time mismatch')
        domain=None;geometry=();errors=()
        def finish(status,receipt=None,baseline=None,covariance=None,labels=(),rows=()):
            valid=baseline is not None
            measurement=CarrierBaselineMeasurement(t,decision,valid,status,
                None if baseline is None else tuple(map(float,baseline)),
                None if covariance is None else tuple(tuple(map(float,r)) for r in covariance),
                tuple(rows),tuple(labels),self.policy.angular_floor_rad if valid else None,
                covariance_model='CONDITIONAL_SOURCE_FIXED_N_GLS_PLUS_REGISTERED_ANGULAR_FLOOR')
            return SetProviderStep(status,domain,geometry,errors,receipt,measurement,len(self._history),time.monotonic()-started)
        if self.terminal:
            self._history=[]
            return finish('SOURCE_TERMINAL_NO_RESURRECTION')
        if decision-self.source.selected_at>self.policy.max_source_age_s:
            self._ended=True;self._history=[]
            return finish('SOURCE_EXPIRED')
        previous_history=self._history
        self._history=[]  # A consumed slot that raises can never preserve a stale streak.
        try:
            domain=self.lifecycle.advance(model,time_s=t,qualified_nodes=qualified_nodes,
                horizontal_axes=horizontal_axes,calls=calls.lifecycle)
        except Exception:
            self._history=[]
            raise
        if domain.retired_nodes:previous_history=[]
        if domain.physically_ended:
            self._ended=True;self._history=[]
            return finish('PHYSICAL_SOURCE_ENDED')
        gs=[];es=[]
        for item in domain.classes:
            calls.consume('geometry')
            try:
                old=cover_from_arcs((item.azimuth_outer_arc,)) if item.cost_compatible else None
                g=sphere_direction_envelope(item.baseline_center_m,item.baseline_covariance_m2,item.raw_budget,
                    horizontal_axes=horizontal_axes,length_interval_m=(self.source.length_m,self.source.length_m),
                    recorded_outer_radius_m=item.baseline_outer_radius_m,legacy_cover=old)
                gs.append(g);es.append('')
            except Exception as exc:
                gs.append(None);es.append(type(exc).__name__+': '+str(exc))
        geometry=tuple(gs);errors=tuple(es)
        compatible=[(i,c) for i,c in enumerate(domain.classes) if c.cost_compatible]
        # Geometry never removes competitors to upgrade this gate.
        if len(compatible)!=1 or not domain.direction_domain_qualified:
            self._history=[]
            return finish('UNRESOLVED_SOURCE_SET_OR_CURRENT_QUALITY')
        index,item=compatible[0];g=geometry[index]
        if g is None or g.cover.empty or g.cover.full_circle or len(g.cover.components)!=1:
            self._history=[]
            return finish('UNQUALIFIED_CURRENT_DIRECTION_DOMAIN')
        # Reconstruct the actual current observation view for an existing origin,
        # not a center-only objective or a forged old primary/competitor receipt.
        origin=min(item.origins)
        graph=next((x for x in self.lifecycle.graphs if x.origin_fingerprint==origin),None)
        if graph is None:raise TemporalModelError('current class origin is absent from frozen source')
        view=transport_epoch(model,graph);block=view.model
        if (block is None or view.relation_projection.integer_items!=item.integer_items
                or model_fingerprint(block)!=domain.transformed_model_fingerprint
                or model_fingerprint(model)!=domain.current_model_fingerprint):
            self._history=[]
            raise TemporalModelError('current observation/graph identity mismatch')
        calls.consume('sphere')
        try:
            sphere=constrained_baseline(item.baseline_center_m,np.array(item.baseline_covariance_m2),self.source.length_m)
            baseline=np.asarray(sphere.baseline,float)
            n=np.array([dict(item.integer_items)[l] for l in block.ambiguity_labels],float)
            residual=np.asarray(block.y)-np.asarray(block.A)@n-np.asarray(block.B)@baseline
            white=np.linalg.solve(np.linalg.cholesky(block.Q),residual)
            rawcost=float(white@white)
            delta=baseline-np.asarray(item.baseline_center_m)
            identity=item.residual_cost+float(delta@np.linalg.solve(item.baseline_covariance_m2,delta))
            error=abs(rawcost-identity)
            tolerance=self.policy.lifecycle.absolute_cost_guard+self.policy.lifecycle.relative_numerical_guard*max(1.,rawcost,abs(identity))
            if (not np.isfinite(baseline).all() or not math.isfinite(rawcost) or not math.isfinite(identity)
                    or abs(np.linalg.norm(baseline)-self.source.length_m)>1e-9*self.source.length_m
                    or error>tolerance or sphere.hard_case):
                self._history=[]
                return finish('UNQUALIFIED_SPHERE_POINT_NUMERICS_OR_NONUNIQUENESS')
        except Exception:
            self._history=[]
            raise
        if rawcost>item.expanded_raw_threshold:
            self._history=[]
            return finish('CURRENT_SPHERE_POINT_OUTSIDE_ORIGINAL_COST_DOMAIN')
        epoch=SetValidationEpoch(t,domain.current_model_fingerprint,domain.transformed_model_fingerprint,
            _domain_fingerprint(domain),item.origins,item.integer_items,rawcost,item.expanded_raw_threshold,error)
        proposed=(previous_history+[epoch])[-self.policy.validation_epochs:]
        common=set(proposed[0].class_origins)
        for e in proposed[1:]:common.intersection_update(e.class_origins)
        # One physical frozen origin must explain every slot. Alternating classes
        # cannot borrow each other's accumulated singleton status.
        if not common:
            self._history=[epoch]
            return finish('VALIDATION_ORIGIN_CHANGED')
        self._history=proposed
        if len(proposed)<self.policy.validation_epochs:return finish('VALIDATING_CONDITIONAL_SOURCE_SET')
        receipt=SetValidationReceipt(self.source.fingerprint,self.source.selected_at,self.source_available_at_s,
            self.source.length_m,tuple(proposed),tuple(sorted(common)),decision)
        if t!=decision:return finish('INTERNAL_CATCHUP_NOT_EXPORTED',receipt)
        covariance=positive_definite(np.array(item.baseline_covariance_m2)+np.eye(3)*
            (self.source.length_m*self.policy.angular_floor_rad)**2,'conditional source point engineering covariance')
        return finish('RESEARCH_CONDITIONAL_SOURCE_SET_POINT',receipt,baseline,covariance,
            block.ambiguity_labels,range(len(block.y)))
