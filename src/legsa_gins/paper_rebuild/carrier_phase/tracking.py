"""Causal rolling validation of an unchanged previously exported integer pair.

No integer search, covariance tuning, subset shrink, candidate swap, time
rewriting, or resurrection is performed. Repeated overlapping passes condition
on earlier survival; nominal per-window tests are not a lifetime guarantee or
false-fix probability. Native fusion ownership belongs to the replay controller.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass,asdict,is_dataclass
import hashlib,json,math
import numpy as np
from .admission import (FrozenCandidate,AdmissionConfig,AdmissionEpoch,CandidateGate,
    CausalAdmissionSession,score_frozen_epoch,gate_candidate_records)
from .temporal import TemporalModelError,model_fingerprint,assemble_epochs
from .faults import build_phase_fault_map,stack_phase_fault_maps,fixed_integer_gls,single_fault_glrt
from .measurement import (CarrierBaselineMeasurement,BoundFaultDiagnosis,
    diagnose_validated_window,qualify_current_baseline,qualify_tracking_baseline,
    unavailable_measurement)


def _plain(value):
    if is_dataclass(value):return _plain(asdict(value))
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {str(k):_plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [_plain(v) for v in value]
    return value


def receipt_fingerprint(value):
    return hashlib.sha256(json.dumps(_plain(value),sort_keys=True,separators=(",",":"),
                                     allow_nan=False).encode()).hexdigest()


def diagnostic_model_fingerprint(model):
    # Numeric epoch identity alone intentionally omits signal/group metadata.
    # Bind the actual derived physical-SD fault map as well for this receipt.
    return receipt_fingerprint((model_fingerprint(model),build_phase_fault_map(model)))


@dataclass(frozen=True)
class TrackingConfig:
    fault_family_alpha: float=.01
    angular_floor_rad: float=math.radians(1.5)

    def __post_init__(self):
        if (not math.isfinite(self.fault_family_alpha) or not 0<self.fault_family_alpha<1
                or not math.isfinite(self.angular_floor_rad)
                or not 0<self.angular_floor_rad<math.pi/2):
            raise TemporalModelError("invalid registered tracking measurement/diagnostic policy")


@dataclass(frozen=True)
class TrackingBinding:
    """Immutable origin policy supplied by the active track, not by a receipt."""
    origin_id: str
    primary_fingerprint: str
    competitor_fingerprint: str
    selected_at: float
    tracking_started_at: float
    admission_config: AdmissionConfig
    tracking_config: TrackingConfig


@dataclass(frozen=True)
class TrackingWindowReceipt:
    origin_id: str
    previous_receipt_fingerprint: str
    primary_fingerprint: str
    competitor_fingerprint: str
    origin_selected_at: float
    tracking_started_at: float
    step_index: int
    expected_times: tuple[float,...]
    observed_times: tuple[float,...]
    ordered_model_fingerprints: tuple[str,...]
    diagnostic_model_fingerprints: tuple[str,...]
    epochs: tuple[AdmissionEpoch,...]
    primary: CandidateGate|None
    competitor: CandidateGate|None
    diagnosis: BoundFaultDiagnosis|None
    admission_config: AdmissionConfig
    tracking_config: TrackingConfig
    policy_fingerprint: str
    status: str
    experimental_passed: bool
    false_fix_probability: None=None
    production_validated: bool=False
    independent_repeated_acceptances: bool=False
    assumptions: tuple[str,...]=(
        "fixed-N Gaussian working Q; no integer-correctness guarantee",
        "overlapping windows and survival-conditioned validation are not independent",
        "no track-lifetime or cross-track false-alarm/false-fix calibration",
        "measurement covariance omits integer error and selection conditioning")

    @property
    def fingerprint(self):return receipt_fingerprint(self)


@dataclass(frozen=True)
class TrackingStep:
    time_s: float
    status: str
    terminal: bool
    measurement: CarrierBaselineMeasurement
    receipt: TrackingWindowReceipt|None


def _phase_support(model,record):
    if record.reason is not None:return record.reason
    rows=np.asarray(record.rows_retained,dtype=int)
    phase=rows[np.any(np.asarray(model.A)[rows]!=0,axis=1)]
    if len(phase)<4 or np.linalg.matrix_rank(np.asarray(model.B)[phase])!=3:
        return "UNRESOLVED_PHASE_REDUNDANCY_OR_GEOMETRY"
    return None


def _window_status(records,primary,competitor,diagnosis):
    if any(r.reason for r in records):return next(r.reason for r in records if r.reason)
    if primary is None or competitor is None:return "UNRESOLVED_INSUFFICIENT_VALIDATION"
    if not primary.residual_pass:return "REJECTED_RESIDUAL"
    if not primary.length_pass:return "REJECTED_LENGTH"
    if competitor.passes:return "UNRESOLVED_COMPETITION"
    if diagnosis is None:return "UNRESOLVED_PHASE_DIAGNOSTIC"
    value=diagnosis.diagnosis
    if not value.scores or value.tested_hypotheses<=0:return "UNRESOLVED_NO_TESTABLE_PHASE_FAULT_HYPOTHESES"
    if any(s.nominal_reject_null for s in value.scores):return "REJECTED_PHASE_FAULT_DIAGNOSTIC"
    return "EXPERIMENTAL_TRACKING_ACCEPTED"


def validate_tracking_receipt(model,candidate,receipt,*,binding,availability_time_s):
    """Detect semantic/input mismatches; not an attestation against hostile code."""
    if not isinstance(binding,TrackingBinding):raise TemporalModelError("active tracking origin binding required")
    if ((receipt.origin_id,receipt.primary_fingerprint,receipt.competitor_fingerprint,
         receipt.origin_selected_at,receipt.tracking_started_at,receipt.admission_config,receipt.tracking_config)
            !=(binding.origin_id,binding.primary_fingerprint,binding.competitor_fingerprint,
               binding.selected_at,binding.tracking_started_at,binding.admission_config,binding.tracking_config)):
        raise TemporalModelError("tracking receipt differs from active origin/policy binding")
    config=binding.admission_config;policy=binding.tracking_config
    if (candidate.fingerprint!=receipt.primary_fingerprint
            or candidate.selected_at!=receipt.origin_selected_at):
        raise TemporalModelError("tracking candidate differs from unchanged origin")
    if receipt.policy_fingerprint!=receipt_fingerprint((config,policy)):
        raise TemporalModelError("tracking policy changed after validation")
    if (not isinstance(receipt.step_index,int) or receipt.step_index<1
            or not isinstance(receipt.origin_id,str) or len(receipt.origin_id)!=64
            or not isinstance(receipt.previous_receipt_fingerprint,str)
            or len(receipt.previous_receipt_fingerprint)!=64):
        raise TemporalModelError("tracking origin/step identity required")
    expected=tuple(candidate.selected_at+(receipt.step_index+i+1)*config.epoch_interval_s
                   for i in range(config.validation_epochs))
    observed=tuple(r.time_s for r in receipt.epochs)
    fp=tuple(r.model_fingerprint for r in receipt.epochs)
    if (receipt.expected_times!=expected or receipt.observed_times!=observed
            or len(observed)!=config.validation_epochs
            or len(receipt.diagnostic_model_fingerprints)!=len(observed)
            or any(t<=candidate.selected_at for t in observed)
            or any(b<=a for a,b in zip(observed,observed[1:]))
            or any(abs(a-b)>config.time_tolerance_s for a,b in zip(expected,observed))
            or receipt.ordered_model_fingerprints!=fp
            or any(not isinstance(v,str) or len(v)!=64 for v in fp)
            or receipt.tracking_started_at>=observed[-1]):
        raise TemporalModelError("tracking receipt does not bind the registered rolling slots")
    if (not math.isfinite(availability_time_s) or availability_time_s!=float(model.time_s)
            or observed[-1]!=float(model.time_s)
            or model_fingerprint(model)!=fp[-1]
            or diagnostic_model_fingerprint(model)!=receipt.diagnostic_model_fingerprints[-1]):
        raise TemporalModelError("tracking measurement must match the current bound model")
    if model.metadata.get("baseline_frame")!="ECEF":raise TemporalModelError("tracking baseline frame must be ECEF")
    if receipt.experimental_passed:
        recomputed_primary=gate_candidate_records(candidate.candidate_id,receipt.epochs,"primary",alpha_total=config.alpha_total)
        recomputed_competitor=(None if receipt.competitor is None else gate_candidate_records(
            receipt.competitor.candidate_id,receipt.epochs,"competitor",alpha_total=config.alpha_total))
        if (receipt_fingerprint(recomputed_primary)!=receipt_fingerprint(receipt.primary)
                or receipt_fingerprint(recomputed_competitor)!=receipt_fingerprint(receipt.competitor)):
            raise TemporalModelError("tracking gate summary differs from bound epoch fits")
        diag=receipt.diagnosis
        if (not config.independent_epoch_working_model
                or any(r.validated_active_labels!=candidate.active_labels for r in receipt.epochs)
                or diag is None or diag.candidate_fingerprint!=candidate.fingerprint
                or diag.ordered_model_fingerprints!=fp
                or diag.diagnosis.family_alpha!=policy.fault_family_alpha
                or diag.diagnosis.accepted_integer_measurement
                or receipt.status!=_window_status(receipt.epochs,receipt.primary,receipt.competitor,diag)
                or receipt.status!="EXPERIMENTAL_TRACKING_ACCEPTED"):
            raise TemporalModelError("tracking receipt lacks bound passing gates/diagnostics")


class FixedCandidateTrack:
    """One owner candidate, terminal on first missing/invalid/rejected next slot.

    Start revalidates the original receipt from its actual five models; the
    initial exported measurement is NOT re-emitted. Epoch slots stay anchored
    at the original selected_at, preventing tolerance drift. Models are copied
    to isolate later caller mutations. Only five current models are retained.
    """
    @classmethod
    def start(cls,primary,competitor,origin_models,origin_admission,origin_diagnosis,
              origin_measurement,*,admission_config,tracking_config=TrackingConfig()):
        if admission_config.validation_epochs!=5:
            raise TemporalModelError("this tracking policy requires exactly five validation epochs")
        if not admission_config.independent_epoch_working_model:
            raise TemporalModelError("tracking requires declared independent-epoch working Q")
        models=tuple(deepcopy(m) for m in origin_models)
        if len(models)!=5:raise TemporalModelError("five original validation models required")
        session=CausalAdmissionSession(primary,competitor,admission_config)
        for model in models:session.observe(model)
        admission=session.finalize()
        if receipt_fingerprint(admission)!=receipt_fingerprint(origin_admission):
            raise TemporalModelError("origin admission does not reproduce with original pair/config/models")
        if not admission.shadow_accepted:raise TemporalModelError("origin primary was not admitted")
        for model,record in zip(models,admission.epochs):
            failure=_phase_support(model,record)
            if failure:raise TemporalModelError("origin tracking support: "+failure)
        diagnosis=diagnose_validated_window(models,primary,admission,
                                           family_alpha=tracking_config.fault_family_alpha)
        if receipt_fingerprint(diagnosis)!=receipt_fingerprint(origin_diagnosis):
            raise TemporalModelError("origin diagnosis or diagnostic policy does not reproduce")
        measurement=qualify_current_baseline(models[-1],primary,admission,diagnosis,
            length_m=admission_config.length_m,angular_floor_rad=tracking_config.angular_floor_rad,
            availability_time_s=float(models[-1].time_s))
        if not measurement.valid or receipt_fingerprint(measurement)!=receipt_fingerprint(origin_measurement):
            raise TemporalModelError("origin current measurement or covariance floor does not reproduce")
        self=cls.__new__(cls)
        self._primary=primary;self._competitor=competitor
        self._config=admission_config;self._policy=tracking_config
        self._models=list(models);self._state="ACTIVE";self._step=0
        self._start=float(models[-1].time_s);self._last=self._start
        self._origin=receipt_fingerprint((primary,competitor,admission,diagnosis,measurement,
                                         admission_config,tracking_config))
        self._previous=self._origin;self._terminal_step=None
        self._policy_fp=receipt_fingerprint((admission_config,tracking_config))
        self._binding=TrackingBinding(self._origin,primary.fingerprint,competitor.fingerprint,
                                     primary.selected_at,self._start,admission_config,tracking_config)
        return self

    @property
    def state(self):return self._state
    @property
    def origin_id(self):return self._origin
    @property
    def primary(self):return self._primary
    @property
    def binding(self):return self._binding
    @property
    def competitor(self):return self._competitor
    @property
    def last_accepted_time_s(self):return self._last
    @property
    def next_expected_time_s(self):
        return self._primary.selected_at+(self._config.validation_epochs+self._step+1)*self._config.epoch_interval_s

    def _release(self,time_s,reason,receipt=None):
        self._state="RELEASED"
        self._terminal_step=TrackingStep(float(time_s),reason,True,
                                        unavailable_measurement(float(time_s),reason),receipt)
        return self._terminal_step

    def missing(self,time_s,reason="MISSING_CURRENT_MODEL"):
        if self._state!="ACTIVE":raise TemporalModelError("released tracking origin cannot resume")
        if not math.isfinite(time_s):
            self._release(self.next_expected_time_s,"INVALID_CURRENT_TIME")
            raise TemporalModelError("finite tracking event time required; track released")
        return self._release(time_s,"RELEASED_"+str(reason))

    def observe(self,model,*,availability_time_s):
        if self._state!="ACTIVE":raise TemporalModelError("released tracking origin cannot resume")
        expected=self.next_expected_time_s;event_time=expected
        try:
            t=float(model.time_s)
            if math.isfinite(t):event_time=t
            if (not math.isfinite(t) or not math.isfinite(availability_time_s)
                    or availability_time_s!=t or t<=self._last
                    or abs(t-expected)>self._config.time_tolerance_s):
                return self._release(t if math.isfinite(t) else expected,"RELEASED_TIME_SLOT_OR_AVAILABILITY")
            current=deepcopy(model)
            window=tuple((*self._models[1:],current));step_index=self._step+1
            times=tuple(self._primary.selected_at+(step_index+i+1)*self._config.epoch_interval_s
                        for i in range(self._config.validation_epochs))
            records=tuple(score_frozen_epoch(m,self._primary,self._competitor,slot_index=i,
                minimum_phase_rows=self._config.minimum_phase_rows,length_m=self._config.length_m)
                for i,m in enumerate(window))
            for m,record in zip(window,records):
                failure=_phase_support(m,record)
                if failure:return self._release(t,"RELEASED_"+failure)
            primary=gate_candidate_records(self._primary.candidate_id,records,"primary",alpha_total=self._config.alpha_total)
            competitor=gate_candidate_records(self._competitor.candidate_id,records,"competitor",alpha_total=self._config.alpha_total)
            fingerprints=tuple(model_fingerprint(m) for m in window)
            problem=assemble_epochs(window,length_m=self._config.length_m)
            rows=tuple(part.start+r for part,record in zip(problem.row_slices,records) for r in record.rows_retained)
            fit=fixed_integer_gls(problem,self._primary.integers,rows=rows)
            if fit.rows_retained!=rows:raise TemporalModelError("tracking diagnostic support mismatch")
            mapping=stack_phase_fault_maps(tuple(build_phase_fault_map(m) for m in window),persistent=True)
            diag=BoundFaultDiagnosis(self._primary.fingerprint,fingerprints,
                single_fault_glrt(fit,mapping,family_alpha=self._policy.fault_family_alpha))
            status=_window_status(records,primary,competitor,diag)
            receipt=TrackingWindowReceipt(self._origin,self._previous,self._primary.fingerprint,
                self._competitor.fingerprint,self._primary.selected_at,self._start,step_index,times,
                tuple(m.time_s for m in window),fingerprints,
                tuple(diagnostic_model_fingerprint(m) for m in window),records,primary,competitor,diag,
                self._config,self._policy,self._policy_fp,status,status=="EXPERIMENTAL_TRACKING_ACCEPTED")
            measurement=qualify_tracking_baseline(current,self._primary,receipt,binding=self._binding,availability_time_s=t)
            if not measurement.valid:return self._release(t,"RELEASED_"+measurement.status,receipt)
            self._models=list(window);self._step=step_index;self._last=t;self._previous=receipt.fingerprint
            return TrackingStep(t,status,False,measurement,receipt)
        except (TemporalModelError,ValueError,TypeError,AttributeError,np.linalg.LinAlgError) as exc:
            return self._release(event_time,"RELEASED_INVALID_CURRENT_MODEL_OR_RECEIPT:"+str(exc))
