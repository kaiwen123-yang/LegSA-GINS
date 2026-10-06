"""Causal future-epoch score of already selected integers, with a moving baseline.

This is a predictive diagnostic, not a calibrated integer acceptance policy.
No new integer is searched, future observations cannot change the input N,
and rows depending on unknown or reset arcs are explicitly withheld.
"""
from dataclasses import dataclass
from typing import Mapping
import numpy as np
from ..horizontal_literature.ext01_clambda import constrained_baseline
from .temporal import EpochBlock, TemporalModelError, positive_definite

@dataclass(frozen=True)
class FutureEpochScore:
    time_s: float
    decision_time_s: float
    rows_retained: tuple[int,...]
    rows_withheld: tuple[int,...]
    known_phase_rows: int
    unknown_labels: tuple[str,...]
    baseline_m: np.ndarray
    residual_cost: float
    whitened_residuals: np.ndarray
    length_error_m: float
    baseline_rank: int
    nominal_residual_dimension: int
    accepted_integer_measurement: bool = False

def score_future_epoch(block: EpochBlock, integers: Mapping[str,int], *,
                       decision_time_s: float, length_m: float,
                       minimum_known_phase_rows: int = 3) -> FutureEpochScore:
    """Fit only free b on the sphere using retained future observations.

    Matching identities include both receiver arcs and the pivot. Taking a
    covariance principal submatrix is the correct marginal for withheld rows;
    filling reset-arc integers with zero or an old integer is forbidden.
    The nominal residual dimension is n-2 for a regular 2D sphere, not a
    claim that this nonlinear, selected-candidate score has a chi-square law.
    """
    if not np.isfinite(block.time_s) or not np.isfinite(decision_time_s) or block.time_s <= decision_time_s:
        raise TemporalModelError("future validation must be after the integer decision time")
    if not np.isfinite(length_m) or length_m<=0 or minimum_known_phase_rows<1:
        raise TemporalModelError("invalid future validation configuration")
    labels=tuple(block.ambiguity_labels)
    y=np.asarray(block.y,float);A=np.asarray(block.A,float);B=np.asarray(block.B,float)
    Q=positive_definite(block.Q,"future Q")
    if (y.ndim!=1 or A.shape!=(len(y),len(labels)) or B.shape!=(len(y),3)
        or Q.shape!=(len(y),len(y)) or len(set(labels))!=len(labels)
        or not all(np.isfinite(x).all() for x in (y,A,B))):
        raise TemporalModelError("invalid future epoch dimensions or values")
    known=np.array([label in integers for label in labels])
    vector=np.zeros(len(labels))
    for i,label in enumerate(labels):
        if not known[i]:continue
        value=integers[label]
        if (isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,np.integer))
            or abs(int(value))>2**53-1):
            raise TemporalModelError("future candidate must contain exactly represented integers")
        vector[i]=value
    withheld=np.any(A[:,~known]!=0,axis=1)
    retained=np.flatnonzero(~withheld)
    phase_count=int(np.sum(np.any(A[retained]!=0,axis=1)))
    if phase_count<minimum_known_phase_rows:
        raise TemporalModelError("insufficient future phase rows on candidate arcs")
    q=Q[np.ix_(retained,retained)];chol=np.linalg.cholesky(q)
    target=np.linalg.solve(chol,(y-A@vector)[retained])
    design=np.linalg.solve(chol,B[retained])
    u,s,vt=np.linalg.svd(design,full_matrices=False)
    rank=int(np.sum(s>np.finfo(float).eps*max(design.shape)*s[0]))
    if rank!=3:raise TemporalModelError("future baseline geometry is rank deficient")
    center=vt.T@((u.T@target)/s)
    covariance=(vt.T/(s*s))@vt
    sphere=constrained_baseline(center,covariance,length_m)
    residual=target-design@sphere.baseline
    return FutureEpochScore(float(block.time_s),float(decision_time_s),tuple(map(int,retained)),
        tuple(map(int,np.flatnonzero(withheld))),phase_count,
        tuple(label for label,k in zip(labels,known) if not k),
        sphere.baseline,float(residual@residual),residual,
        abs(float(np.linalg.norm(sphere.baseline))-length_m),rank,len(retained)-2)

def compare_future_scores(first, second):
    """Compare only identical scored epochs/rows; unavailable is never zero cost."""
    left={x.time_s:x for x in first};right={x.time_s:x for x in second}
    if len(left)!=len(first) or len(right)!=len(second):
        raise TemporalModelError("duplicate future scoring epoch")
    common=[t for t in sorted(set(left)&set(right))
            if left[t].rows_retained==right[t].rows_retained]
    if not common:
        return {"status":"NO_COMMON_SCORED_SUPPORT","common_times":[],
                "first_cost":None,"second_cost":None,"second_minus_first":None,
                "complete_matching_support":False}
    a=sum(left[t].residual_cost for t in common)
    b=sum(right[t].residual_cost for t in common)
    return {"status":"COMMON_SUPPORT_SCORED","common_times":common,
            "first_cost":a,"second_cost":b,"second_minus_first":b-a,
            "complete_matching_support":len(common)==len(first)==len(second)}
