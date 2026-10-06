"""Current-time experimental carrier-baseline measurements for native fusion.

A valid flag means the registered engineering gates passed, not physical FIX
truth or a calibrated false-fix probability. The exported engineering working
covariance retains unconstrained fixed-N GLS Cb plus an explicit isotropic floor;
it is not the exact covariance of the nonlinear sphere-projected mean. It omits
discrete integer errors, gate-selection conditioning and unmodelled phase faults.
"""
from dataclasses import dataclass
import math
from typing import Sequence
import numpy as np
from .admission import FrozenCandidate,AdmissionDecision
from .faults import (FaultDiagnosis,fixed_integer_gls,build_phase_fault_map,
                     stack_phase_fault_maps,single_fault_glrt)
from .multignss import MultiGnssEpoch
from .temporal import (EpochBlock,TemporalModelError,positive_definite,
                       model_fingerprint,assemble_epochs)
from ..horizontal_literature.ext01_clambda import constrained_baseline

CSV_FIELDS=("measurement_time","decision_available_time","b_ecef_x","b_ecef_y","b_ecef_z",
 "cov_xx","cov_xy","cov_xz","cov_yx","cov_yy","cov_yz","cov_zx","cov_zy","cov_zz","valid")

@dataclass(frozen=True)
class CarrierBaselineMeasurement:
    measurement_time: float
    decision_available_time: float
    valid: bool
    status: str
    baseline_ecef_m: tuple[float,...]|None=None
    covariance_ecef_m2: tuple[tuple[float,...],...]|None=None
    retained_rows: tuple[int,...]=()
    fixed_labels: tuple[str,...]=()
    angular_floor_rad: float|None=None
    covariance_model: str="FIXED_INTEGER_GLS_PLUS_REGISTERED_ISOTROPIC_ANGULAR_FLOOR"
    integer_truth_known: bool=False
    calibrated_false_fix_probability: None=None
    production_validated: bool=False

    def csv_row(self):
        values=[self.measurement_time,self.decision_available_time]
        if self.valid:
            values.extend(self.baseline_ecef_m)
            values.extend(x for row in self.covariance_ecef_m2 for x in row)
        else:
            values.extend([""]*12)
        values.append(int(self.valid))
        return dict(zip(CSV_FIELDS,values))

@dataclass(frozen=True)
class BoundFaultDiagnosis:
    """A diagnostic result tied to one candidate and ordered validation window."""
    candidate_fingerprint: str
    ordered_model_fingerprints: tuple[str,...]
    diagnosis: FaultDiagnosis


def _receipt_fingerprints(admission:AdmissionDecision):
    values=tuple(epoch.model_fingerprint for epoch in admission.epochs)
    if (not admission.complete_future_support or not values
            or len(values)!=len(admission.expected_future_times)
            or len(values)!=len(admission.observed_future_times)
            or any(not isinstance(value,str) or len(value)!=64 for value in values)
            or tuple(epoch.time_s for epoch in admission.epochs)!=admission.observed_future_times):
        raise TemporalModelError("complete bound admission model receipts required")
    return values


def diagnose_validated_window(models:Sequence[MultiGnssEpoch],candidate:FrozenCandidate,
                              admission:AdmissionDecision,*,family_alpha:float=.01)->BoundFaultDiagnosis:
    """Diagnose exactly the admitted models/support; no reference or N revision.

    A constant-cycle fault alternative is shared only across identical explicit
    SD arc tokens. Full within-epoch Q and the admission's exact common-known
    row support are retained; epoch independence is the admission working model.
    Rejected candidates can be diagnosed, but diagnosis cannot promote them.
    """
    models=tuple(models)
    expected=_receipt_fingerprints(admission)
    if candidate.fingerprint!=admission.primary_fingerprint:
        raise TemporalModelError("diagnostic candidate differs from the admitted primary")
    if (len(models)!=len(expected)
            or tuple(model_fingerprint(m) for m in models)!=expected
            or tuple(float(m.time_s) for m in models)!=admission.observed_future_times):
        raise TemporalModelError("diagnostic models differ from the bound validation window")
    if (admission.registered_length_m is None
            or not math.isfinite(admission.registered_length_m)
            or admission.registered_length_m<=0):
        raise TemporalModelError("registered admission length required")
    if not admission.independent_epoch_working_model:
        raise TemporalModelError("diagnosis requires the registered independent-epoch Q model")
    problem=assemble_epochs(models,length_m=admission.registered_length_m)
    rows=tuple(part.start+row for part,record in zip(problem.row_slices,admission.epochs)
               for row in record.rows_retained)
    fit=fixed_integer_gls(problem,candidate.integers,rows=rows)
    if fit.rows_retained!=rows:
        raise TemporalModelError("diagnostic candidate does not reproduce admission support")
    fault_map=stack_phase_fault_maps(tuple(build_phase_fault_map(m) for m in models),
                                    persistent=True)
    diagnosis=single_fault_glrt(fit,fault_map,family_alpha=family_alpha)
    return BoundFaultDiagnosis(candidate.fingerprint,expected,diagnosis)


def unavailable_measurement(time_s:float,reason:str):
    if not math.isfinite(time_s) or not isinstance(reason,str) or not reason:
        raise TemporalModelError("finite event time and explicit rejection reason required")
    return CarrierBaselineMeasurement(float(time_s),float(time_s),False,reason)


def qualify_current_baseline(model:EpochBlock, candidate:FrozenCandidate,
                             admission:AdmissionDecision, diagnosis:BoundFaultDiagnosis,*,
                             length_m:float, angular_floor_rad:float,
                             availability_time_s:float)->CarrierBaselineMeasurement:
    """Export only the final bound future epoch, with no delayed/backdated update.

    The mean is constrained to registered L. Cb plus floor is an engineering
    working covariance, not an exact projected covariance or a calibrated bound.
    """
    if (not math.isfinite(length_m) or length_m<=0 or not math.isfinite(angular_floor_rad)
            or angular_floor_rad<=0 or angular_floor_rad>=math.pi/2):
        raise TemporalModelError("positive physical length and registered angular floor required")
    if (not math.isfinite(availability_time_s) or availability_time_s!=float(model.time_s)):
        raise TemporalModelError("only current-time decisions supported; no backdating or delayed fusion")
    t=float(model.time_s)
    if candidate.fingerprint!=admission.primary_fingerprint:
        raise TemporalModelError("baseline candidate differs from the validated frozen primary")
    if model.metadata.get("baseline_frame")!="ECEF":
        raise TemporalModelError("baseline model must explicitly use ECEF coordinates")
    if not admission.shadow_accepted:
        return unavailable_measurement(t,admission.status)
    if (not admission.complete_future_support or not admission.observed_future_times
            or admission.observed_future_times[-1]!=t
            or admission.unvalidated_selected_labels
            or admission.shadow_candidate_id!=candidate.candidate_id):
        raise TemporalModelError("accepted decision does not support this current measurement")
    if admission.registered_length_m is None or length_m!=admission.registered_length_m:
        raise TemporalModelError("measurement length differs from the registered admission length")
    expected=_receipt_fingerprints(admission)
    if model_fingerprint(model)!=expected[-1]:
        raise TemporalModelError("current model differs from the bound last validation epoch")
    if (not isinstance(diagnosis,BoundFaultDiagnosis)
            or diagnosis.candidate_fingerprint!=candidate.fingerprint
            or diagnosis.ordered_model_fingerprints!=expected
            or not isinstance(diagnosis.diagnosis,FaultDiagnosis)
            or diagnosis.diagnosis.accepted_integer_measurement):
        raise TemporalModelError("candidate and full-window bound diagnostic-only phase result required")
    result=diagnosis.diagnosis
    if not result.scores or result.tested_hypotheses<=0:
        return unavailable_measurement(t,"UNRESOLVED_NO_TESTABLE_PHASE_FAULT_HYPOTHESES")
    if any(score.nominal_reject_null for score in result.scores):
        return unavailable_measurement(t,"REJECTED_PHASE_FAULT_DIAGNOSTIC")
    fit=fixed_integer_gls(model,candidate.integers,rows=admission.epochs[-1].rows_retained)
    rows=np.asarray(fit.rows_retained,dtype=int)
    phase_rows=rows[np.any(np.asarray(model.A)[rows]!=0,axis=1)]
    if len(phase_rows)<4 or np.linalg.matrix_rank(np.asarray(model.B)[phase_rows])!=3:
        return unavailable_measurement(t,"UNRESOLVED_PHASE_REDUNDANCY_OR_GEOMETRY")
    if fit.baseline_rank!=3:
        return unavailable_measurement(t,"UNRESOLVED_BASELINE_RANK")
    sphere=constrained_baseline(fit.bhat,fit.Cb,length_m)
    covariance=positive_definite(fit.Cb+np.eye(3)*(length_m*angular_floor_rad)**2,"carrier covariance")
    if not np.isfinite(sphere.baseline).all():
        return unavailable_measurement(t,"UNRESOLVED_NONFINITE_BASELINE")
    return CarrierBaselineMeasurement(t,t,True,"EXPERIMENTAL_FIXED_CANDIDATE",
        tuple(map(float,sphere.baseline)),tuple(tuple(map(float,row)) for row in covariance),
        tuple(map(int,fit.rows_retained)),candidate.active_labels,float(angular_floor_rad))
