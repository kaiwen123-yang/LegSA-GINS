"""Fixed-N geometry/working-Q sensitivity to physical SD phase biases.

This module never changes integers, observations, or admission thresholds.
MDB refers to the specified scalar residual test under a known Gaussian Q,
correct fixed N and mean model. It is NOT integer correctness, a false-fix
probability, a heading protection level, or physical fault-source certification.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm,ncx2
from .faults import FixedIntegerGLS,PhaseFaultMap
from .temporal import TemporalModelError,positive_definite

@dataclass(frozen=True)
class PhaseFaultSensitivity:
    key: str
    status: str
    information_cycles_inverse2: float
    baseline_gain_m_per_cycle: tuple[float,...]
    baseline_gain_norm_m_per_cycle: float
    per_epoch_gain_norm_m_per_cycle: tuple[float,...]
    mdb_cycles: float|None
    mdb_power: float|None
    mdb_baseline_bias_m: tuple[float,...]|None
    mdb_joint_bias_norm_m: float|None
    mdb_per_epoch_bias_norm_m: tuple[float,...]|None
    mdb_max_epoch_bias_norm_m: float|None
    detectable_amplitude_unbounded: bool
    observational_aliases: tuple[str,...]

@dataclass(frozen=True)
class SensitivityAnalysis:
    scores: tuple[PhaseFaultSensitivity,...]
    rows_retained: tuple[int,...]
    nuisance_dimension: int
    epoch_count: int
    family_hypotheses: int
    estimable_hypotheses: int
    family_alpha: float
    per_hypothesis_alpha: float
    miss_probability: float
    two_sided_z_threshold: float
    chi_square_one_threshold: float
    required_noncentrality: float
    observability_tolerance: float
    working_model: str="CORRECT_FIXED_N_KNOWN_GAUSSIAN_Q_AND_CORRECT_LINEAR_MEAN"
    family_definition: str="ALL_SUPPLIED_PHYSICAL_SIGNAL_COLUMNS_INCLUDING_UNOBSERVABLE_AND_ALIASED"
    scope: str="FREE_BASELINE_GEOMETRY_SENSITIVITY_NOT_SPHERE_OR_HEADING_PROTECTION"
    false_fix_probability: None=None
    integer_correctness_established: bool=False
    accepted_integer_measurement: bool=False

def _power_noncentrality(threshold:float,target_power:float,miss_probability:float)->float:
    null_power=float(ncx2.sf(threshold,1,0.))
    if not null_power<target_power<1.:
        raise TemporalModelError("requested power must exceed the scalar null rejection probability")
    high=max(1.,(math.sqrt(threshold)+float(norm.isf(miss_probability)))**2)
    while float(ncx2.sf(threshold,1,high))<target_power:
        high*=2
        if high>1e12:raise TemporalModelError("could not bracket the specified scalar-test power")
    return float(brentq(lambda value:float(ncx2.sf(threshold,1,value))-target_power,
                        0.,high,xtol=1e-12,rtol=1e-12))

def analyze_phase_fault_sensitivity(fit:FixedIntegerGLS,fault_map:PhaseFaultMap,*,
                                   family_alpha:float=.01,miss_probability:float=.05,
                                   observability_tolerance:float=1e-10)->SensitivityAnalysis:
    """Return one scalar-test MDB and induced free-b bias per physical column.

    f is metres per cycle in original observation coordinates. With L L'=Q,
    B_w=L^-1 B and f_w=L^-1 f, h=||P_perp f_w||^2 and
    g=Cb B_w' f_w (metres/cycle). A cycle bias a induces mean shift a*g,
    and scalar-test noncentrality a^2*h. g concerns unconstrained GLS only:
    the fitted sphere baseline and heading have different nonlinear responses.

    Bonferroni divides alpha among ALL supplied columns, retaining aliases and
    unobservable hypotheses in the denominator. It is a conservative specified
    per-signal test, not the data-adaptive Holm detector used elsewhere.
    A zero-information direction has no finite MDB; null is serialized with an
    explicit unbounded flag instead of a fabricated finite number.
    """
    if (not math.isfinite(family_alpha) or not 0<family_alpha<1
            or not math.isfinite(miss_probability) or not 0<miss_probability<1
            or not math.isfinite(observability_tolerance) or not 0<observability_tolerance<.01):
        raise TemporalModelError("invalid sensitivity probability or rank tolerance")
    p=fit.nuisance_dimension;n=len(fit.rows_retained)
    if p<3 or p%3 or fit.baseline_rank!=p:
        raise TemporalModelError("sensitivity requires full-rank 3K free-baseline nuisance; a pseudoinverse is insufficient")
    B=np.asarray(fit.whitened_design,float);basis=np.asarray(fit.nuisance_basis,float)
    chol=np.asarray(fit.cholesky,float);cb=positive_definite(fit.nuisance_covariance,"sensitivity Cb")
    if (B.shape!=(n,p) or basis.shape!=(n,p) or cb.shape!=(p,p) or chol.shape!=(n,n)
            or not all(np.isfinite(x).all() for x in (B,basis,chol))):
        raise TemporalModelError("inconsistent fixed-integer fit dimensions or nonfinite values")
    if fit.original_row_count!=fault_map.original_row_count:
        raise TemporalModelError("fault map and fixed-integer model row identities differ")
    matrix=np.asarray(fault_map.matrix,float);keys=tuple(h.key for h in fault_map.hypotheses)
    if (not keys or len(set(keys))!=len(keys) or matrix.shape!=(len(fault_map.row_indices),len(keys))
            or not np.isfinite(matrix).all()):
        raise TemporalModelError("invalid fault-map columns or hypothesis identities")
    selected=fault_map.subset(fit.rows_retained).matrix
    white=np.linalg.solve(chol,selected)
    projected=white-basis@(basis.T@white)
    raw_norm=np.linalg.norm(white,axis=0);residual_norm=np.linalg.norm(projected,axis=0)
    if not np.isfinite(raw_norm).all() or not np.isfinite(residual_norm).all():
        raise TemporalModelError("nonfinite whitened fault information")
    estimable=(raw_norm>0)&(residual_norm>observability_tolerance*raw_norm)
    if fit.residual_df<=0:estimable[:]=False
    information=residual_norm**2
    gains=cb@(B.T@white)
    if not np.isfinite(gains).all():raise TemporalModelError("nonfinite free-baseline sensitivity gain")
    count=len(keys);alpha=family_alpha/count
    z=float(norm.isf(alpha/2.));threshold=z*z
    if not math.isfinite(threshold):raise TemporalModelError("scalar threshold is not representable")
    noncentrality=_power_noncentrality(threshold,1.-miss_probability,miss_probability)
    unit=np.zeros_like(projected)
    unit[:,estimable]=projected[:,estimable]/residual_norm[estimable]
    scores=[]
    for j,key in enumerate(keys):
        gain=gains[:,j];epoch_gain=np.linalg.norm(gain.reshape(-1,3),axis=1)
        aliases=tuple(keys[k] for k in np.flatnonzero(estimable)
                      if estimable[j] and min(np.linalg.norm(unit[:,j]-unit[:,k]),
                                              np.linalg.norm(unit[:,j]+unit[:,k]))<=observability_tolerance)
        amplitude=power=bias=joint=per_epoch=maximum=None
        if estimable[j]:
            amplitude=math.sqrt(noncentrality)/float(residual_norm[j])
            bias=gain*amplitude;per_epoch=np.linalg.norm(bias.reshape(-1,3),axis=1)
            joint=float(np.linalg.norm(bias));maximum=float(np.max(per_epoch))
            power=float(ncx2.sf(threshold,1,(amplitude*residual_norm[j])**2))
            if not math.isfinite(amplitude) or not np.isfinite(bias).all():
                raise TemporalModelError("finite scalar information produced unrepresentable MDB")
        scores.append(PhaseFaultSensitivity(key,"ESTIMABLE" if estimable[j] else "UNDETECTABLE",
            float(information[j]),tuple(map(float,gain)),float(np.linalg.norm(gain)),tuple(map(float,epoch_gain)),
            amplitude,power,None if bias is None else tuple(map(float,bias)),joint,
            None if per_epoch is None else tuple(map(float,per_epoch)),maximum,not bool(estimable[j]),aliases))
    return SensitivityAnalysis(tuple(scores),tuple(fit.rows_retained),p,p//3,count,int(np.sum(estimable)),
        float(family_alpha),alpha,float(miss_probability),z,threshold,noncentrality,float(observability_tolerance))
