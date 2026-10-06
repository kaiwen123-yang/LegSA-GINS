"""One-shot causal shadow admission of frozen carrier integer candidates.

Only future observations enter the validation statistic. The registered working
model is independent Gaussian epoch noise with known Q and correct geometry.
Nominal correct-candidate Type-I levels are NOT false-fix probabilities.

For fixed true N, free-baseline GLS gives S_k ~ chi2(n_k-3). If the
true baseline has registered length L, the sphere distance D_k is no
greater than (bhat_k-btrue_k)' Cb_k^-1 (bhat_k-btrue_k) ~ chi2(3).
Independent epochs therefore give an exact chi2(sum(n_k-3)) residual
gate and a conservative chi2(3K) length-distance gate. Splitting alpha
between these gates is a Bonferroni bound on rejecting a correct fixed
candidate under the working model. It says nothing about an incorrect
integer passing, omitted alternative candidates, or model misspecification.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,math
from typing import Mapping
import numpy as np
from scipy.stats import chi2
from ..horizontal_literature.ext01_clambda import constrained_baseline
from .temporal import EpochBlock,TemporalModelError,model_fingerprint

@dataclass(frozen=True)
class FrozenCandidate:
    candidate_id: str
    selected_at: float
    integer_items: tuple[tuple[str,int],...]
    active_labels: tuple[str,...]
    source_id: str

    def __post_init__(self):
        items=tuple((label,value) for label,value in self.integer_items)
        labels=tuple(self.active_labels)
        if (not isinstance(self.candidate_id,str) or not self.candidate_id
                or not isinstance(self.source_id,str) or not self.source_id
                or not math.isfinite(self.selected_at)):
            raise TemporalModelError("candidate identity and finite selection time required")
        if (not items or len({x[0] for x in items})!=len(items)
                or any(not isinstance(label,str) or not label for label,_ in items)):
            raise TemporalModelError("candidate integer labels must be nonempty and unique")
        for _,value in items:
            if (isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,np.integer))
                    or abs(int(value))>2**53-1):
                raise TemporalModelError("candidate requires exact supported integer values")
        if not labels or len(set(labels))!=len(labels) or any(s not in dict(items) for s in labels):
            raise TemporalModelError("all active labels must be unique and frozen with the candidate")
        object.__setattr__(self,"integer_items",tuple(sorted((s,int(n)) for s,n in items)))
        object.__setattr__(self,"active_labels",labels)
        object.__setattr__(self,"selected_at",float(self.selected_at))

    @classmethod
    def from_mapping(cls,candidate_id:str,selected_at:float,integers:Mapping[str,int],
                     active_labels:tuple[str,...],source_id:str):
        return cls(candidate_id,selected_at,tuple(integers.items()),tuple(active_labels),source_id)

    @property
    def integers(self):
        """Return a fresh copy, never mutable state used by the session."""
        return dict(self.integer_items)

    @property
    def fingerprint(self):
        value=(self.candidate_id,self.selected_at,self.integer_items,self.active_labels,self.source_id)
        return hashlib.sha256(json.dumps(value,separators=(",",":")).encode()).hexdigest()

@dataclass(frozen=True)
class AdmissionConfig:
    validation_epochs: int=5
    epoch_interval_s: float=.2
    time_tolerance_s: float=.01
    minimum_phase_rows: int=3
    length_m: float=.350
    alpha_total: float=.01
    independent_epoch_working_model: bool=True

    def __post_init__(self):
        if (isinstance(self.validation_epochs,bool) or not isinstance(self.validation_epochs,int)
                or self.validation_epochs<1 or isinstance(self.minimum_phase_rows,bool)
                or not isinstance(self.minimum_phase_rows,int) or self.minimum_phase_rows<1):
            raise TemporalModelError("positive integer validation and phase-row counts required")
        for value in (self.epoch_interval_s,self.time_tolerance_s,self.length_m,self.alpha_total):
            if not math.isfinite(value) or value<=0:raise TemporalModelError("invalid admission configuration")
        if self.alpha_total>=1 or self.time_tolerance_s>=self.epoch_interval_s/2:
            raise TemporalModelError("invalid Type-I level or overlapping validation slots")
        if not isinstance(self.independent_epoch_working_model,bool):
            raise TemporalModelError("independence working-model flag must be boolean")

@dataclass(frozen=True)
class CandidateEpochFit:
    residual_cost: float
    residual_df: int
    length_penalty: float
    sphere_full_cost: float
    baseline_center_m: tuple[float,...]
    baseline_covariance_m2: tuple[tuple[float,...],...]
    baseline_length_m: float
    rows_retained: tuple[int,...]
    rank: int

@dataclass(frozen=True)
class AdmissionEpoch:
    time_s: float
    slot_index: int
    rows_retained: tuple[int,...]
    rows_withheld: tuple[int,...]
    validated_active_labels: tuple[str,...]
    unknown_labels: tuple[str,...]
    primary: CandidateEpochFit|None
    competitor: CandidateEpochFit|None
    reason: str|None
    model_fingerprint: str=""

@dataclass(frozen=True)
class CandidateGate:
    candidate_id: str
    residual_cost: float
    residual_df: int
    residual_threshold: float
    residual_nominal_p_value: float
    residual_pass: bool
    length_penalty: float
    length_bound_df: int
    length_threshold: float
    length_conservative_nominal_p_value: float
    length_pass: bool
    sphere_full_cost: float

    @property
    def passes(self):return self.residual_pass and self.length_pass

@dataclass(frozen=True)
class AdmissionDecision:
    status: str
    shadow_accepted: bool
    shadow_candidate_id: str|None
    selected_at: float
    expected_future_times: tuple[float,...]
    observed_future_times: tuple[float,...]
    complete_future_support: bool
    validated_labels: tuple[str,...]
    unvalidated_selected_labels: tuple[str,...]
    primary: CandidateGate|None
    competitor: CandidateGate|None
    epochs: tuple[AdmissionEpoch,...]
    reasons: tuple[str,...]
    primary_fingerprint: str
    competitor_fingerprint: str
    alpha_correct_candidate_nominal_type_i: float
    independent_epoch_working_model: bool
    assumptions: tuple[str,...]
    false_fix_probability: None=None
    accepted_integer_measurement: bool=False
    all_integer_alternatives_tested: bool=False
    registered_length_m: float|None=None

class CausalAdmissionSession:
    """Freeze two candidates and consume a fixed future horizon exactly once.

    A failed primary is never replaced by the competitor using this same
    validation data. Missing time slots cannot be replaced by later samples.
    No public interim acceptance exists; finalize ends the session permanently.
    """
    def __init__(self,primary:FrozenCandidate,competitor:FrozenCandidate,
                 config:AdmissionConfig=AdmissionConfig()):
        if primary.selected_at!=competitor.selected_at:
            raise TemporalModelError("both candidates must be frozen at the same decision time")
        if primary.active_labels!=competitor.active_labels:
            raise TemporalModelError("competitors must use identical selected active-label support")
        if primary.candidate_id==competitor.candidate_id:
            raise TemporalModelError("candidate identifiers must distinguish the two frozen hypotheses")
        self._primary=primary;self._competitor=competitor;self._config=config
        self._times=tuple(primary.selected_at+(i+1)*config.epoch_interval_s for i in range(config.validation_epochs))
        self._records={};self._last_time=primary.selected_at;self._closed=False
        p=primary.integers;c=competitor.integers
        self._same_active_class=all(p[label]==c[label] for label in primary.active_labels)

    @property
    def state(self):return "FINALIZED" if self._closed else "COLLECTING"

    @property
    def expected_future_times(self):return self._times

    def _fit(self,block,integer_mapping,rows):
        return fit_candidate_epoch(block,integer_mapping,rows,length_m=self._config.length_m)

    def observe(self,block:EpochBlock)->AdmissionEpoch:
        if self._closed:raise TemporalModelError("admission session already finalized")
        t=float(block.time_s)
        if not math.isfinite(t) or t<=self._primary.selected_at or t<=self._last_time:
            raise TemporalModelError("validation must be strictly future and strictly time ordered")
        nearest=int(np.argmin(np.abs(np.asarray(self._times)-t)))
        if abs(self._times[nearest]-t)>self._config.time_tolerance_s:
            raise TemporalModelError("observation is outside the registered future validation slots")
        if nearest in self._records:raise TemporalModelError("duplicate validation slot")
        self._last_time=t
        record=score_frozen_epoch(block,self._primary,self._competitor,slot_index=nearest,
                                  minimum_phase_rows=self._config.minimum_phase_rows,length_m=self._config.length_m)
        self._records[nearest]=record
        return record

    def _gate(self,candidate,records,attribute):
        return gate_candidate_records(candidate.candidate_id,records,attribute,alpha_total=self._config.alpha_total)

    def finalize(self)->AdmissionDecision:
        if self._closed:raise TemporalModelError("admission session already finalized")
        self._closed=True;records=tuple(self._records[k] for k in sorted(self._records))
        complete=len(records)==self._config.validation_epochs
        validated=set(self._primary.active_labels)
        if not records:validated.clear()
        for record in records:validated.intersection_update(record.validated_active_labels)
        if not complete:validated.clear()
        valid=tuple(label for label in self._primary.active_labels if label in validated)
        unvalidated=tuple(label for label in self._primary.active_labels if label not in validated)
        primary=self._gate(self._primary,records,"primary")
        competitor=self._gate(self._competitor,records,"competitor")
        reasons=tuple(dict.fromkeys(record.reason for record in records if record.reason is not None))
        if not self._config.independent_epoch_working_model:
            status="UNRESOLVED_MODEL_UNSUPPORTED"
        elif not complete:
            status="UNRESOLVED_MISSING_FUTURE_SUPPORT"
        elif self._same_active_class:
            status="UNRESOLVED_SAME_ACTIVE_CLASS"
        elif unvalidated:
            status="UNRESOLVED_ACTIVE_ARC_CHANGED"
        elif reasons or primary is None or competitor is None:
            status="UNRESOLVED_INSUFFICIENT_VALIDATION"
        elif not primary.residual_pass and not primary.length_pass:
            status="REJECTED_RESIDUAL_AND_LENGTH"
        elif not primary.residual_pass:
            status="REJECTED_RESIDUAL"
        elif not primary.length_pass:
            status="REJECTED_LENGTH"
        elif competitor.passes:
            status="UNRESOLVED_COMPETITION"
        else:
            status="SHADOW_ACCEPTED"
        accepted=status=="SHADOW_ACCEPTED"
        return AdmissionDecision(status,accepted,self._primary.candidate_id if accepted else None,
            self._primary.selected_at,self._times,tuple(r.time_s for r in records),complete,valid,unvalidated,
            primary,competitor,records,reasons,self._primary.fingerprint,self._competitor.fingerprint,
            self._config.alpha_total,self._config.independent_epoch_working_model,
            ("registered Q is known and correctly specified","Gaussian errors",
             "epochs and validation versus selection noise are independent",
             "geometry and fixed length are correct","the registered fixed future horizon is used once",
             "only the registered competitor is tested; no full integer posterior mass"),
            None,False,False,registered_length_m=float(self._config.length_m))


def fit_candidate_epoch(block,integer_mapping,rows,*,length_m):
    # Import locally so this state API can be inspected without the optional
    # fault-diagnostic implementation importing the entire pipeline.
    from .faults import fixed_integer_gls
    fit=fixed_integer_gls(block,integer_mapping,rows=rows)
    if fit.baseline_rank!=3 or fit.residual_df!=len(fit.rows_retained)-3:
        raise TemporalModelError("future free-baseline rank must be exactly three")
    if fit.residual_df<=0:raise TemporalModelError("no positive future residual dimension")
    center=np.asarray(fit.nuisance_estimate,float);cov=np.asarray(fit.nuisance_covariance,float)
    sphere=constrained_baseline(center,cov,length_m)
    return CandidateEpochFit(float(fit.residual_cost),int(fit.residual_df),float(sphere.objective),
        float(fit.residual_cost+sphere.objective),tuple(map(float,center)),
        tuple(tuple(map(float,row)) for row in cov),float(np.linalg.norm(center)),
        tuple(map(int,fit.rows_retained)),int(fit.baseline_rank))


def gate_candidate_records(candidate_id,records,attribute,*,alpha_total):
    fits=[getattr(record,attribute) for record in records]
    if not fits or any(fit is None for fit in fits):return None
    residual=sum(f.residual_cost for f in fits);df=sum(f.residual_df for f in fits)
    length=sum(f.length_penalty for f in fits);length_df=3*len(fits);alpha=alpha_total/2
    return CandidateGate(candidate_id,residual,df,float(chi2.isf(alpha,df)),
        float(chi2.sf(residual,df)),bool(residual<=chi2.isf(alpha,df)),
        length,length_df,float(chi2.isf(alpha,length_df)),float(chi2.sf(length,length_df)),
        bool(length<=chi2.isf(alpha,length_df)),sum(f.sphere_full_cost for f in fits))


def score_frozen_epoch(block,primary,competitor,*,slot_index,minimum_phase_rows,length_m):
    labels=tuple(block.ambiguity_labels);A=np.asarray(block.A,float);y=np.asarray(block.y,float)
    if (y.ndim!=1 or A.shape!=(len(y),len(labels)) or not np.isfinite(A).all()
            or len(set(labels))!=len(labels)):
        raise TemporalModelError("invalid future ambiguity design")
    p=primary.integers;c=competitor.integers
    common_known=np.array([label in p and label in c for label in labels],dtype=bool)
    withheld=np.any(A[:,~common_known]!=0,axis=1)
    rows=tuple(map(int,np.flatnonzero(~withheld)))
    phase_count=int(np.sum(np.any(A[list(rows)]!=0,axis=1)))
    observed_labels={labels[i] for i in range(len(labels)) if np.any(A[list(rows),i]!=0)}
    validated=tuple(label for label in primary.active_labels if label in observed_labels)
    unknown=tuple(label for label,known in zip(labels,common_known) if not known)
    reason=None;pf=cf=None
    if len(validated)!=len(primary.active_labels):
        reason="UNRESOLVED_ACTIVE_ARC_CHANGED"
    if phase_count<minimum_phase_rows:
        reason=reason or "UNRESOLVED_INSUFFICIENT_PHASE_SUPPORT"
    if phase_count>=minimum_phase_rows:
        try:
            pf=fit_candidate_epoch(block,p,rows,length_m=length_m);cf=fit_candidate_epoch(block,c,rows,length_m=length_m)
            if pf.rows_retained!=cf.rows_retained or pf.rows_retained!=rows:
                pf=cf=None;reason="UNRESOLVED_UNMATCHED_SUPPORT"
        except (TemporalModelError,np.linalg.LinAlgError,ValueError) as exc:
            reason=reason or "UNRESOLVED_GEOMETRY_OR_MODEL: "+str(exc)
            pf=cf=None
    record=AdmissionEpoch(float(block.time_s),slot_index,rows,tuple(map(int,np.flatnonzero(withheld))),validated,unknown,pf,cf,reason,
                          model_fingerprint(block))
    return record
