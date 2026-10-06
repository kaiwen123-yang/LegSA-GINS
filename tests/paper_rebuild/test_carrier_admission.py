"""Deterministic causal admission checks; no real data or integer search calls."""
import math
from dataclasses import FrozenInstanceError
import numpy as np
import pytest
from scipy.stats import chi2
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock,TemporalModelError
from legsa_gins.paper_rebuild.carrier_phase.admission import (
    FrozenCandidate,AdmissionConfig,CausalAdmissionSession)

LABELS=("a","b","c")
N=np.array([2,-1,4])
L=.350
WAVE=.190293672798365

def candidate(name="best",delta=0,active=LABELS,old=None):
    n=dict(zip(LABELS,map(int,N)));n["a"]+=delta
    if old is not None:n["historical_arc"]=old
    return FrozenCandidate.from_mapping(name,0.,n,active,"registered-test-source")

def block(index,*,noise_scale=.01,baseline_length=L,offset=None,labels=LABELS):
    B=np.vstack((np.eye(3),np.eye(3)));A=np.vstack((np.zeros((3,3)),WAVE*np.eye(3)))
    yaw=.2*index
    b=baseline_length*np.array([np.cos(yaw),np.sin(yaw),0.])
    y=B@b+A@N
    if offset is not None:y=y+offset
    return EpochBlock(.2*(index+1),y,A,B,np.eye(6)*noise_scale**2,labels)

def session(config=None,first=None,second=None):
    return CausalAdmissionSession(first or candidate(),second or candidate("second",2),
                                  config or AdmissionConfig())

def feed(s,blocks=None):
    for b in blocks or [block(i) for i in range(5)]:s.observe(b)
    return s.finalize()

def test_causal_nominal_accepts_only_shadow_and_separates_competitor():
    d=feed(session())
    assert d.status=="SHADOW_ACCEPTED" and d.shadow_accepted
    assert d.shadow_candidate_id=="best"
    assert d.validated_labels==LABELS and not d.unvalidated_selected_labels
    assert d.primary.residual_df==15 and d.primary.length_bound_df==15
    assert d.primary.residual_cost<1e-20 and d.primary.length_penalty<1e-20
    assert d.primary.residual_threshold==pytest.approx(chi2.isf(.005,15))
    assert not (d.competitor.residual_pass and d.competitor.length_pass)
    assert d.false_fix_probability is None
    assert d.accepted_integer_measurement is False
    assert d.all_integer_alternatives_tested is False

def test_both_plausible_is_unresolved_not_ratio_acceptance():
    d=feed(session(),[block(i,noise_scale=1.) for i in range(5)])
    assert d.primary.passes and d.competitor.passes
    assert d.status=="UNRESOLVED_COMPETITION" and not d.shadow_accepted

def test_residual_rejection_uses_free_baseline_orthogonal_component():
    offset=np.r_[np.array([.5,0,0]),np.array([-.5,0,0])]
    d=feed(session(),[block(i,offset=offset) for i in range(5)])
    # With isotropic Q and duplicated I, opposite code/phase offsets cannot
    # enter the fitted baseline: exactly 2*0.5^2/sigma^2 per epoch.
    assert d.primary.residual_cost==pytest.approx(25000.)
    assert d.primary.length_penalty<1e-20
    assert d.status=="REJECTED_RESIDUAL"

def test_length_rejection_is_not_hidden_by_zero_free_gls_residual():
    d=feed(session(),[block(i,baseline_length=.7) for i in range(5)])
    # Center covariance is sigma^2/2 I, so the exact sphere distance is analytic.
    expected=5*(.7-L)**2/(.01**2/2)
    assert d.primary.residual_cost<1e-20
    assert d.primary.length_penalty==pytest.approx(expected)
    assert d.status=="REJECTED_LENGTH"

def test_both_rejection_and_no_validation_driven_candidate_swap():
    offset=np.r_[np.array([.5,0,0]),np.array([-.5,0,0])]
    d=feed(session(),[block(i,baseline_length=.7,offset=offset) for i in range(5)])
    assert d.status=="REJECTED_RESIDUAL_AND_LENGTH"
    wrong_primary=session(first=candidate("wrong",2),second=candidate("truth",0))
    d=feed(wrong_primary)
    assert d.status.startswith("REJECTED")
    assert d.shadow_candidate_id is None and d.competitor.passes

def test_same_active_class_with_different_retired_integer_is_unresolved():
    d=feed(session(first=candidate(old=0),second=candidate("second",old=1)))
    assert d.status=="UNRESOLVED_SAME_ACTIVE_CLASS"

def test_changed_arc_is_not_silently_accepted_from_remaining_rows():
    blocks=[block(i) for i in range(5)]
    blocks[2]=block(2,labels=("new_arc","b","c"))
    d=feed(session(),blocks)
    assert d.status=="UNRESOLVED_ACTIVE_ARC_CHANGED"
    assert d.validated_labels==("b","c") and d.unvalidated_selected_labels==("a",)
    assert d.epochs[2].unknown_labels==("new_arc",)
    assert d.epochs[2].rows_withheld==(3,)

def test_additional_unknown_arc_rows_withheld_with_covariance_principal_submatrix():
    blocks=[]
    for i in range(5):
        b=block(i)
        A=np.zeros((7,4));A[:6,:3]=b.A;A[6,3]=WAVE
        B=np.vstack((b.B,[.2,.3,.4]));y=np.r_[b.y,999.]
        Q=np.eye(7)*.0001;Q[0,6]=Q[6,0]=.00002
        blocks.append(EpochBlock(b.time_s,y,A,B,Q,LABELS+("unselected_new_arc",)))
    d=feed(session(),blocks)
    assert d.status=="SHADOW_ACCEPTED"
    assert all(x.rows_withheld==(6,) for x in d.epochs)
    assert d.primary.residual_cost<1e-20

def test_missing_slot_is_not_replaced_by_later_epoch():
    s=session()
    for i in (0,2,3,4):s.observe(block(i))
    d=s.finalize()
    assert d.status=="UNRESOLVED_MISSING_FUTURE_SUPPORT"
    assert not d.validated_labels and d.unvalidated_selected_labels==LABELS
    s=session()
    with pytest.raises(TemporalModelError,match="outside"):s.observe(block(5))

def test_no_before_selection_duplicates_or_out_of_order():
    s=session();b=block(0)
    bad=EpochBlock(0.,b.y,b.A,b.B,b.Q,b.ambiguity_labels)
    with pytest.raises(TemporalModelError,match="strictly future"):s.observe(bad)
    s.observe(b)
    with pytest.raises(TemporalModelError,match="strictly future"):s.observe(b)
    s.observe(block(2))
    with pytest.raises(TemporalModelError,match="strictly future"):s.observe(block(1))

def test_no_optional_stopping_or_repeated_use_of_validation_window():
    s=session();s.observe(block(0));d=s.finalize()
    assert d.status=="UNRESOLVED_MISSING_FUTURE_SUPPORT"
    with pytest.raises(TemporalModelError,match="already finalized"):s.observe(block(1))
    with pytest.raises(TemporalModelError,match="already finalized"):s.finalize()

def test_candidate_mapping_is_copied_and_frozen():
    integers=dict(zip(LABELS,map(int,N)))
    c=FrozenCandidate.from_mapping("test",0.,integers,LABELS,"source")
    original=c.fingerprint;integers["a"]=999
    exposed=c.integers;exposed["a"]=888
    assert c.integers["a"]==2 and c.fingerprint==original
    with pytest.raises(FrozenInstanceError):c.selected_at=.2

@pytest.mark.parametrize("bad",[True,1.5,2**53,float("nan")])
def test_invalid_candidate_values_rejected(bad):
    with pytest.raises(TemporalModelError):
        FrozenCandidate.from_mapping("bad",0.,{"a":bad},("a",),"source")

def test_known_unsupported_temporal_noise_model_cannot_admit():
    d=feed(session(config=AdmissionConfig(independent_epoch_working_model=False)))
    assert d.status=="UNRESOLVED_MODEL_UNSUPPORTED" and not d.shadow_accepted

def test_rank_deficiency_stays_unresolved():
    blocks=[block(i) for i in range(5)]
    blocks=[EpochBlock(b.time_s,b.y,b.A,np.zeros_like(b.B),b.Q,b.ambiguity_labels) for b in blocks]
    d=feed(session(),blocks)
    assert d.status=="UNRESOLVED_INSUFFICIENT_VALIDATION"
    assert d.primary is None

def test_length_statistic_is_bounded_by_true_baseline_mahalanobis_error():
    # A deterministic finite-noise perturbation checks the geometric inequality,
    # not a Monte Carlo risk estimate. Chi-square 3K is a conservative bound.
    noise=np.array([.01,-.004,.005,.003,.001,-.002])
    s=session();blocks=[block(i,offset=noise*(i+1)) for i in range(5)]
    for b in blocks:s.observe(b)
    d=s.finalize();upper=0.
    for i,ep in enumerate(d.epochs):
        true=L*np.array([np.cos(.2*i),np.sin(.2*i),0.])
        delta=np.array(ep.primary.baseline_center_m)-true
        upper+=float(delta@np.linalg.solve(np.array(ep.primary.baseline_covariance_m2),delta))
        assert ep.primary.sphere_full_cost==pytest.approx(ep.primary.residual_cost+ep.primary.length_penalty)
    assert d.primary.length_penalty<=upper+1e-8
