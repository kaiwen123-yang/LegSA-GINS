"""Current continuous domains of a complete *conditional source* integer set.

No integer search, phase repair, source likelihood replacement, or acceptance.
Only physical arc retirement changes source relations. A rejected current
observation does not delete an origin, and significant-fault alternatives are
not removed to manufacture a narrower direction union. Per-class Holm is the
existing conditional diagnostic, not a joint/lifecycle risk statement.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import hashlib
import json
import math
from numbers import Integral
import time
import numpy as np
from scipy.stats import chi2

from .admission import FrozenCandidate
from .arc_relations import FrozenIntegerGraph, SdArcNode
from .arc_projection import transport_epoch
from .candidate_envelope import CircularArc, enclosing_arc
from .faults import (PhaseFaultMap, FaultDiagnosis, build_phase_fault_map,
                     fixed_integer_gls, single_fault_glrt)
from .temporal import TemporalModelError, model_fingerprint


@dataclass(frozen=True)
class LifecycleConfig:
    length_m: float = .35
    working_raw_coverage: float = .99
    phase_family_alpha: float = .01
    min_phase_rows: int = 4
    epoch_interval_s: float = .2
    time_tolerance_s: float = .01
    absolute_cost_guard: float = 1e-9
    relative_numerical_guard: float = 1e-10
    max_condition_number: float = 1e12

    def __post_init__(self):
        if (not math.isfinite(self.length_m) or self.length_m <= 0
                or not 0 < self.working_raw_coverage < 1
                or not 0 < self.phase_family_alpha < 1
                or type(self.min_phase_rows) is not int or self.min_phase_rows < 1
                or not math.isfinite(self.epoch_interval_s) or self.epoch_interval_s <= 0
                or not 0 < self.time_tolerance_s < self.epoch_interval_s/2
                or not math.isfinite(self.absolute_cost_guard) or self.absolute_cost_guard <= 0
                or not 0 < self.relative_numerical_guard < 1e-3
                or not math.isfinite(self.max_condition_number) or self.max_condition_number <= 1):
            raise TemporalModelError('invalid lifecycle working-model policy')


@dataclass(frozen=True)
class CompleteSourceSet:
    source_id: str
    selected_at: float
    labels: tuple[str, ...]
    integers: tuple[tuple[int, ...], ...]
    problem_fingerprint: str
    support_complete: bool
    source_raw_threshold: float
    length_m: float = .35
    likelihood_scope: str = 'SELECTED_OBSERVATION_MARGINAL_Q_V1_LENGTH_NECESSARY_SUPPORT'

    def __post_init__(self):
        if (not self.support_complete or not isinstance(self.source_id,str) or not self.source_id
                or not isinstance(self.problem_fingerprint,str) or len(self.problem_fingerprint)!=64
                or not math.isfinite(self.selected_at) or not self.labels
                or len(set(self.labels))!=len(self.labels)
                or not math.isfinite(self.source_raw_threshold) or self.source_raw_threshold < 0
                or not math.isfinite(self.length_m) or self.length_m <= 0
                or len(set(self.integers))!=len(self.integers)):
            raise TemporalModelError('complete unique bound source set required')
        for vector in self.integers:
            if len(vector)!=len(self.labels) or any(isinstance(x,bool) or not isinstance(x,Integral)
                    or abs(int(x))>2**53-1 for x in vector):
                raise TemporalModelError('source contains invalid exact integer vector')
        # Validate labels even for the legitimate empty source.
        from .arc_relations import DdArcRelation
        for label in self.labels:
            DdArcRelation.from_label(label)

    @property
    def fingerprint(self):
        payload=(self.source_id,self.selected_at,self.labels,self.integers,
                 self.problem_fingerprint,self.source_raw_threshold,self.length_m,self.likelihood_scope)
        return hashlib.sha256(json.dumps(payload,separators=(',',':')).encode()).hexdigest()

    @classmethod
    def from_saved_record(cls, record, *, source_id, registered_length_m):
        raw=record['raw_envelope'];length=record['length_necessary_support']
        if (not raw['numerical_support_complete'] or not length['raw_support_complete']
                or not length['necessary_support_complete']
                or raw['problem_fingerprint']!=length['problem_fingerprint']):
            raise TemporalModelError('saved source support incomplete or fingerprint mismatch')
        if raw['status'] not in ('COMPLETE_RELAXED_SUPPORT','EMPTY_RELAXED_SUPPORT'):
            raise TemporalModelError('saved source is not a complete enumerated domain')
        raw_vectors={tuple(item['integer']) for item in raw['candidates']}
        vectors=tuple(tuple(item['integer']) for item in length['retained_candidates'])
        kept={tuple(item['integer']) for item in length['items'] if item['retained']}
        if (set(vectors)!=kept or not kept<=raw_vectors
                or length['raw_observed_candidates']!=len(raw_vectors)
                or tuple(record['selection']['selected_labels'])!=tuple(raw['ambiguity_labels'])
                or record['selection']['selected_at']!=raw['target_time_s']):
            raise TemporalModelError('saved source candidate/support identity mismatch')
        return cls(source_id,float(raw['target_time_s']),tuple(raw['ambiguity_labels']),
                   vectors,raw['problem_fingerprint'],True,float(raw['raw_cost_threshold']),float(registered_length_m))


@dataclass
class LifecycleCalls:
    gls_limit: int = 115
    glrt_limit: int = 115
    fixed_integer_gls_calls: int = 0
    single_fault_glrt_calls: int = 0
    deadline_monotonic: float | None = None

    def consume(self, kind):
        if self.deadline_monotonic is not None and time.monotonic()>self.deadline_monotonic:
            raise TemporalModelError('lifecycle processing deadline reached; no retry')
        count,limit=('fixed_integer_gls_calls','gls_limit') if kind=='gls' else ('single_fault_glrt_calls','glrt_limit')
        if getattr(self,count)>=getattr(self,limit):
            raise TemporalModelError('lifecycle call budget exhausted: '+kind)
        setattr(self,count,getattr(self,count)+1)


@dataclass(frozen=True)
class PhaseEffect:
    key: str
    classification: str
    transformed_column_zero: bool
    baseline_gain_m_per_cycle: tuple[float,...]
    baseline_gain_norm_m_per_cycle: float
    residual_information_cycles_inverse2: float
    aliases: tuple[str,...]
    significant: bool


def transported_fault_map(original, view):
    base=build_phase_fault_map(original)
    matrix=view.observation_transform@base.matrix
    if view.model is None:
        raise TemporalModelError('no phase view for current fault diagnosis')
    labels=view.model.ambiguity_labels;aa=view.model.A
    hypotheses=tuple(replace(h,affected_ambiguity_labels=tuple(label for k,label in enumerate(labels)
        if np.any((aa[:,k]!=0)&(matrix[:,j]!=0)))) for j,h in enumerate(base.hypotheses))
    return base,PhaseFaultMap(matrix,hypotheses,tuple(range(len(matrix))),len(matrix))


def classify_phase_effects(fit, fault_map, diagnosis):
    """No MDB computation: retain exact F effect, GLS gain and existing GLRT rank.

    NA requires an exactly zero current observation column AND zero gain. An
    aliased but estimable column remains a normal diagnostic, not a veto.
    """
    selected=fault_map.subset(fit.rows_retained).matrix
    keys=tuple(h.key for h in fault_map.hypotheses)
    if keys!=tuple(s.key for s in diagnosis.scores):
        raise TemporalModelError('fault diagnostic identity mismatch')
    white=np.linalg.solve(fit.cholesky,selected)
    gains=fit.Cb@(fit.whitened_design.T@white)
    if not np.isfinite(gains).all():
        raise TemporalModelError('nonfinite current baseline fault gain')
    effects=[]
    for j,score in enumerate(diagnosis.scores):
        zero=not np.any(selected[:,j]);gain=gains[:,j]
        if zero and not np.any(gain):
            classification='NA_NO_CURRENT_EFFECT'
        elif score.status=='UNOBSERVABLE_AFTER_NUISANCE':
            classification=('DANGEROUS_UNOBSERVABLE_BASELINE_EFFECT' if np.any(gain)
                            else 'UNQUALIFIED_UNOBSERVABLE_NUMERICS')
        else:
            classification='OBSERVABLE_ALIAS' if score.equivalent_hypotheses and len(score.equivalent_hypotheses)>1 else 'OBSERVABLE'
        effects.append(PhaseEffect(score.key,classification,zero,tuple(map(float,gain)),
            float(np.linalg.norm(gain)),score.information_cycles_inverse2,
            score.equivalent_hypotheses,score.nominal_reject_null))
    return tuple(effects)


@dataclass(frozen=True)
class CurrentClassDomain:
    origins: tuple[str,...]
    integer_items: tuple[tuple[str,int],...]
    raw_compatible: bool
    cost_compatible: bool
    residual_cost: float
    raw_threshold: float
    expanded_raw_threshold: float
    raw_budget: float
    baseline_center_m: tuple[float,float,float]
    baseline_covariance_m2: tuple[tuple[float,...],...]
    baseline_outer_radius_m: float | None
    radial_separation_m: float | None
    azimuth_outer_arc: CircularArc | None
    quality_reasons: tuple[str,...]
    phase_diagnosis: FaultDiagnosis
    phase_effects: tuple[PhaseEffect,...]
    baseline_rank: int
    residual_df: int
    condition_number: float


@dataclass(frozen=True)
class CurrentSetDomain:
    source_fingerprint: str
    source_selected_at: float
    time_s: float
    status: str
    quality_status: str
    source_origin_count: int
    physically_ended: bool
    retired_nodes: tuple[SdArcNode,...]
    phase_rows: int
    phase_rank: int
    current_model_fingerprint: str | None
    transformed_model_fingerprint: str | None
    observation_transform: np.ndarray | None
    original_phase_fault_matrix: np.ndarray | None
    transformed_phase_fault_matrix: np.ndarray | None
    classes: tuple[CurrentClassDomain,...]
    compatible_class_count: int
    azimuth_outer_arc: CircularArc | None
    direction_domain_qualified: bool
    all_global_current_alternatives_covered: bool = False
    search_certificate_transferred: bool = False
    accepted_integer_measurement: bool = False
    false_fix_probability: None = None
    scope: str = 'CURRENT_WORKING_DOMAIN_CONDITIONAL_ON_COMPLETE_SAVED_SOURCE_AND_PHYSICAL_ARCS'


def current_class_domain(model, integers, origins, fault_map, horizontal_axes, config, calls,
                         *, phase_rows, phase_rank):
    axes=np.asarray(horizontal_axes,float)
    if (axes.shape!=(2,3) or not np.isfinite(axes).all()
            or np.max(abs(axes@axes.T-np.eye(2)))>1e-12):
        raise TemporalModelError('explicit orthonormal current horizontal axes required')
    if model.metadata.get('baseline_frame')!='ECEF':
        raise TemporalModelError('current lifecycle domain requires declared ECEF model')
    calls.consume('gls');fit=fixed_integer_gls(model,integers)
    if fit.unknown_labels or fit.rows_withheld:
        raise TemporalModelError('current projected class cannot withhold additional unknown rows')
    if (not math.isfinite(fit.residual_cost) or not np.isfinite(fit.bhat).all()
            or not np.isfinite(fit.Cb).all() or not np.isfinite(fit.whitened_residual).all()):
        raise TemporalModelError('nonfinite fixed-integer current domain')
    if fit.baseline_rank!=3 or fit.nuisance_dimension!=3:
        raise TemporalModelError('current continuous domain needs full-rank free 3D baseline')
    condition=float(np.linalg.cond(fit.whitened_design))
    if not math.isfinite(condition) or condition>config.max_condition_number:
        raise TemporalModelError('current domain numerical condition unqualified')
    calls.consume('glrt');diagnosis=single_fault_glrt(fit,fault_map,family_alpha=config.phase_family_alpha)
    effects=classify_phase_effects(fit,fault_map,diagnosis)
    reasons=[]
    if phase_rows<config.min_phase_rows or phase_rank!=3:
        reasons.append('INSUFFICIENT_CURRENT_PHASE_GEOMETRY')
    if any(e.significant for e in effects):reasons.append('PHASE_GLRT_SIGNIFICANT')
    if any(e.classification=='DANGEROUS_UNOBSERVABLE_BASELINE_EFFECT' for e in effects):
        reasons.append('DANGEROUS_UNOBSERVABLE_BASELINE_EFFECT')
    if any(e.classification=='UNQUALIFIED_UNOBSERVABLE_NUMERICS' for e in effects):
        reasons.append('UNQUALIFIED_UNOBSERVABLE_NUMERICS')
    tau=float(chi2.ppf(config.working_raw_coverage,len(model.y)))
    guard=config.absolute_cost_guard+config.relative_numerical_guard*max(1.,tau,abs(fit.residual_cost))
    expanded=tau+guard;rho=expanded-fit.residual_cost
    compatible=rho>=0;radius=separation=arc=None
    raw_compatible=compatible
    center=np.asarray(fit.bhat);cb=np.asarray(fit.Cb);rel=config.relative_numerical_guard
    if compatible:
        eigen=float(np.linalg.eigvalsh(cb)[-1])
        if eigen<=0 or not math.isfinite(eigen):raise TemporalModelError('nonpositive current Cb')
        radius=math.sqrt(rho*eigen*(1+rel))
        scale=max(float(np.linalg.norm(center)),config.length_m,radius,np.finfo(float).tiny)
        radius+=rel*scale
        separation=abs(float(np.linalg.norm(center))-config.length_m)-radius
        compatible=separation<=max(256*np.finfo(float).eps,rel)*scale
        if compatible:
            horizontal=axes@center
            heigen=float(np.linalg.eigvalsh(axes@cb@axes.T)[-1])
            if not math.isfinite(heigen) or heigen<=0:
                raise TemporalModelError('nonpositive or nonfinite current horizontal Cb')
            hradius=math.sqrt(rho*heigen*(1+rel))+rel*max(scale,float(np.linalg.norm(horizontal)))
            hn=float(np.linalg.norm(horizontal))
            if hn<=hradius:
                arc=CircularArc(-math.pi,2*math.pi)
            else:
                half=math.asin(min(1.,hradius/hn))+64*np.finfo(float).eps
                angle=math.atan2(horizontal[1],horizontal[0])
                arc=CircularArc((angle-half+math.pi)%(2*math.pi)-math.pi,min(2*math.pi,2*half))
    return CurrentClassDomain(tuple(sorted(origins)),tuple((l,int(integers[l])) for l in model.ambiguity_labels),
        raw_compatible,compatible,fit.residual_cost,tau,expanded,rho,tuple(map(float,center)),
        tuple(tuple(map(float,row)) for row in cb),radius,separation,arc,tuple(reasons),diagnosis,effects,
        fit.baseline_rank,fit.residual_df,condition)


class ConditionalCandidateSet:
    def __init__(self,source:CompleteSourceSet,config:LifecycleConfig=LifecycleConfig()):
        if config.length_m!=source.length_m:
            raise TemporalModelError('current length differs from source length qualification')
        self.source=source;self.config=config;self.time_s=source.selected_at;self.physically_ended=False
        self.graphs=tuple(FrozenIntegerGraph.from_candidate(FrozenCandidate.from_mapping(
            'source_'+str(i),source.selected_at,dict(zip(source.labels,n)),source.labels,
            source.source_id+':'+source.fingerprint)) for i,n in enumerate(source.integers))
        if self.graphs and any(g.nodes!=self.graphs[0].nodes for g in self.graphs):
            raise TemporalModelError('source hypotheses have different physical supports')

    @property
    def alive_nodes(self):
        return self.graphs[0].nodes if self.graphs else ()

    def advance(self,model,*,time_s,qualified_nodes,horizontal_axes,calls):
        if (not math.isfinite(time_s) or time_s<=self.time_s
                or abs(time_s-self.time_s-self.config.epoch_interval_s)>self.config.time_tolerance_s
                or (model is not None and model.time_s!=time_s)):
            raise TemporalModelError('fixed causal current slot required')
        qualified_nodes=tuple(qualified_nodes)
        before=set(self.alive_nodes)
        self.graphs=tuple(g.advance(qualified_nodes,time_s=time_s) for g in self.graphs)
        self.time_s=float(time_s)
        retired=tuple(sorted(before-set(self.alive_nodes)))
        if self.graphs and not any(len(c)>=2 for c in self.graphs[0].components):
            self.physically_ended=True
        def empty(status):
            return CurrentSetDomain(self.source.fingerprint,self.source.selected_at,self.time_s,status,
                'NO_CURRENT_DIRECTION_DOMAIN',len(self.source.integers),self.physically_ended,retired,
                0,0,None if model is None else model_fingerprint(model),None,None,None,None,(),0,None,False)
        if not self.graphs:return empty('EMPTY_SOURCE')
        if self.physically_ended:return empty('PHYSICAL_SOURCE_ENDED')
        if model is None:return empty('CURRENT_MODEL_UNAVAILABLE')
        views=tuple(transport_epoch(model,g) for g in self.graphs)
        first=views[0]
        for view in views[1:]:
            if (not np.array_equal(view.observation_transform,first.observation_transform)
                    or (view.model is None)!=(first.model is None)):
                raise TemporalModelError('candidate-dependent current observation support')
            if view.model is not None:
                if (view.model.ambiguity_labels!=first.model.ambiguity_labels or any(
                        not np.array_equal(getattr(view.model,name),getattr(first.model,name))
                        for name in ('y','A','B','Q'))):
                    raise TemporalModelError('candidate-dependent current likelihood')
        if first.model is None:return empty('NO_IDENTIFIABLE_CURRENT_PHASE')
        # Exact current integer relations; no residual/angle-based merging.
        classes={}
        for view in views:
            key=view.relation_projection.integer_items
            classes.setdefault(key,[]).append(view.conditional_on_origin)
        original_faults,transformed_faults=transported_fault_map(model,first)
        domains=tuple(current_class_domain(first.model,dict(key),origins,transformed_faults,
            horizontal_axes,self.config,calls,phase_rows=first.phase_rows,phase_rank=first.phase_rank)
            for key,origins in classes.items())
        compatible=tuple(d for d in domains if d.cost_compatible)
        arc=enclosing_arc(d.azimuth_outer_arc for d in compatible)
        qualified=bool(compatible) and all(not d.quality_reasons for d in compatible)
        count=len(compatible)
        status='CURRENT_SET_EMPTY' if count==0 else ('CURRENT_SET_SINGLE' if count==1 else 'CURRENT_SET_MULTI')
        quality=('NO_CURRENT_DIRECTION_DOMAIN' if not compatible else
                 'NUMERICAL_DIRECTION_DOMAIN_READY' if qualified else 'UNQUALIFIED_CURRENT_QUALITY')
        return CurrentSetDomain(self.source.fingerprint,self.source.selected_at,self.time_s,status,quality,
            len(self.source.integers),self.physically_ended,retired,first.phase_rows,first.phase_rank,
            first.original_model_fingerprint,model_fingerprint(first.model),first.observation_transform.copy(),
            original_faults.matrix.copy(),transformed_faults.matrix.copy(),domains,count,arc,qualified)
