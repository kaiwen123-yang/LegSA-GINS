"""Bound admission/diagnosis/export contracts; no integer search or real data."""
from dataclasses import replace
import json
import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate,AdmissionConfig,CausalAdmissionSession
from legsa_gins.paper_rebuild.carrier_phase.temporal import TemporalModelError,model_fingerprint
from legsa_gins.paper_rebuild.carrier_phase.multignss import MultiGnssEpoch,GroupDD,SignalIdentity,signal_spec
from legsa_gins.paper_rebuild.carrier_phase.faults import fixed_integer_gls
from legsa_gins.paper_rebuild.carrier_phase.measurement import (
    qualify_current_baseline,CSV_FIELDS,diagnose_validated_window,BoundFaultDiagnosis)


def fixture(*,partial=False,count=4):
    m=5 if partial else count
    h=np.array([[.5,-.8,.2],[-.7,-.3,.4],[.2,.6,-.8],[.8,.4,.5],[-.4,.1,.9]])[:m]
    pivot=SignalIdentity(0,1,0,0)
    targets=tuple(SignalIdentity(0,i+2,0,0) for i in range(m))
    wave=signal_spec(pivot).wavelength_m
    labels=tuple(json.dumps([f"0:{i+2}:0:0",f"target-arc-{i}","0:1:0:0","pivot-arc"],
                           separators=(",",":")) for i in range(m))
    n=np.array([2,-1,4,0,3])[:m]
    active=labels[:4] if partial else labels
    pair=tuple(FrozenCandidate.from_mapping(name,0.,dict(zip(active,map(int,n[:len(active)]+offset))),
                                            active,"unit")
               for name,offset in [("primary",0),("competitor",100)])
    a=np.vstack((np.zeros((m,m)),wave*np.eye(m)))
    b=np.vstack((h,h))
    scale=np.r_[np.ones(m)*.03,np.ones(m)*.003]
    q=(.5*np.eye(2*m)+.5*np.ones((2*m,2*m)))*scale[:,None]*scale[None,:]
    blocks=[]
    for k in range(5):
        truth=.35*np.array([np.cos(k*.2),np.sin(k*.2),0.])
        y=a@n+b@truth
        group=GroupDD((0,0,0),pivot,targets,y,a,b,q,labels,tuple(range(2*m)),tuple(range(m)))
        blocks.append(MultiGnssEpoch(.2*(k+1),y,a,b,q,labels,(group,),
            {"baseline_frame":"ECEF","receiver_order":"GNSS2_MINUS_GNSS1",
             "arc_label_policy":"EXPLICIT_SD_ARCS"}))
    session=CausalAdmissionSession(*pair,AdmissionConfig())
    for block in blocks:session.observe(block)
    decision=session.finalize()
    assert decision.shadow_accepted
    diag=diagnose_validated_window(blocks,pair[0],decision)
    return blocks,pair,decision,diag


def call(blocks,pair,decision,diag,**kwargs):
    return qualify_current_baseline(blocks[-1],pair[0],decision,diag,
           length_m=kwargs.pop("length_m",.35),angular_floor_rad=np.deg2rad(1.5),
           availability_time_s=kwargs.pop("availability_time_s",blocks[-1].time_s),**kwargs)


def test_export_current_epoch_full_covariance_and_floor():
    blocks,pair,d,diag=fixture()
    out=call(blocks,pair,d,diag)
    assert out.valid and not out.production_validated and out.calibrated_false_fix_probability is None
    assert out.measurement_time==out.decision_available_time==blocks[-1].time_s
    assert tuple(out.csv_row())==CSV_FIELDS and len(out.csv_row())==15
    assert np.linalg.norm(out.baseline_ecef_m)==pytest.approx(.35)
    cb=fixed_integer_gls(blocks[-1],pair[0].integers).Cb
    np.testing.assert_allclose(np.array(out.covariance_ecef_m2)-cb,
                               np.eye(3)*(.35*np.deg2rad(1.5))**2,atol=1e-18)
    assert np.array(out.covariance_ecef_m2)[0,1]==pytest.approx(cb[0,1])
    assert diag.candidate_fingerprint==pair[0].fingerprint
    assert diag.ordered_model_fingerprints==tuple(model_fingerprint(m) for m in blocks)
    assert d.registered_length_m==.35


def test_admission_rejection_retains_event_without_measurement():
    blocks,pair,d,diag=fixture()
    d=replace(d,shadow_accepted=False,status="REJECTED_LENGTH")
    out=call(blocks,pair,d,diag)
    assert not out.valid and out.status=="REJECTED_LENGTH"
    assert list(out.csv_row().values())[2:14]==[""]*12


def test_single_phase_profile_significance_vetoes():
    blocks,pair,d,bound=fixture()
    diag=bound.diagnosis
    diag=replace(diag,scores=(replace(diag.scores[0],nominal_reject_null=True),)+diag.scores[1:])
    out=call(blocks,pair,d,replace(bound,diagnosis=diag))
    assert not out.valid and out.status=="REJECTED_PHASE_FAULT_DIAGNOSTIC"


@pytest.mark.parametrize("kind",["backdate","futuredate","fingerprint","frame","future_support","missing_diag"])
def test_semantic_mismatches_rejected(kind):
    blocks,pair,d,diag=fixture()
    kwargs={}
    if kind=="backdate":kwargs["availability_time_s"]=blocks[-1].time_s-.2
    if kind=="futuredate":kwargs["availability_time_s"]=blocks[-1].time_s+.2
    if kind=="fingerprint":d=replace(d,primary_fingerprint="other")
    if kind=="frame":blocks[-1]=replace(blocks[-1],metadata={"baseline_frame":"NED"})
    if kind=="future_support":d=replace(d,complete_future_support=False)
    if kind=="missing_diag":diag=None
    with pytest.raises(TemporalModelError):call(blocks,pair,d,diag,**kwargs)


def test_less_than_four_phase_rows_not_exported_after_actual_admission():
    blocks,pair,d,diag=fixture(count=3)
    out=call(blocks,pair,d,diag)
    assert not out.valid and out.status=="UNRESOLVED_PHASE_REDUNDANCY_OR_GEOMETRY"


@pytest.mark.parametrize("field",["y","A","B","Q","ambiguity_labels","time_s"])
def test_changed_model_cannot_reuse_old_admission_or_diagnosis(field):
    blocks,pair,d,diag=fixture()
    changed=blocks[-1]
    if field=="ambiguity_labels":
        changed=replace(changed,ambiguity_labels=tuple(reversed(changed.ambiguity_labels)))
    elif field=="time_s":
        changed=replace(changed,time_s=changed.time_s+.001)
    else:
        array=np.array(getattr(changed,field),copy=True)
        array.flat[0]+=.01
        changed=replace(changed,**{field:array})
    blocks[-1]=changed
    with pytest.raises(TemporalModelError):call(blocks,pair,d,diag)
    with pytest.raises(TemporalModelError,match="models differ"):
        diagnose_validated_window(blocks,pair[0],d)


def test_missing_model_receipts_from_old_schema_are_not_exported():
    blocks,pair,d,diag=fixture()
    epochs=tuple(replace(epoch,model_fingerprint="") for epoch in d.epochs)
    old=replace(d,epochs=epochs)
    with pytest.raises(TemporalModelError,match="bound admission"):
        call(blocks,pair,old,diag)
    with pytest.raises(TemporalModelError,match="bound admission"):
        diagnose_validated_window(blocks,pair[0],old)


@pytest.mark.parametrize("kind",["candidate","reverse_window","other_window","unbound"])
def test_diagnostic_must_bind_same_candidate_and_full_ordered_window(kind):
    blocks,pair,d,diag=fixture()
    if kind=="candidate":diag=replace(diag,candidate_fingerprint=pair[1].fingerprint)
    if kind=="reverse_window":diag=replace(diag,ordered_model_fingerprints=tuple(reversed(diag.ordered_model_fingerprints)))
    if kind=="other_window":diag=replace(diag,ordered_model_fingerprints=("f"*64,)+diag.ordered_model_fingerprints[1:])
    if kind=="unbound":diag=diag.diagnosis
    with pytest.raises(TemporalModelError,match="full-window bound"):
        call(blocks,pair,d,diag)


def test_diagnostic_generation_refuses_wrong_candidate_reordered_or_changed_earlier_epoch():
    blocks,pair,d,diag=fixture()
    with pytest.raises(TemporalModelError,match="candidate differs"):
        diagnose_validated_window(blocks,pair[1],d)
    with pytest.raises(TemporalModelError,match="models differ"):
        diagnose_validated_window(tuple(reversed(blocks)),pair[0],d)
    blocks[0]=replace(blocks[0],y=blocks[0].y+.01)
    with pytest.raises(TemporalModelError,match="models differ"):
        diagnose_validated_window(blocks,pair[0],d)


@pytest.mark.parametrize("empty", [True,False])
def test_empty_or_unobservable_diagnosis_is_unresolved_not_clean(empty):
    blocks,pair,d,bound=fixture()
    diag=replace(bound.diagnosis,scores=() if empty else bound.diagnosis.scores,
                 tested_hypotheses=0)
    out=call(blocks,pair,d,replace(bound,diagnosis=diag))
    assert not out.valid and out.status=="UNRESOLVED_NO_TESTABLE_PHASE_FAULT_HYPOTHESES"


def test_export_length_cannot_differ_from_admission_or_be_absent():
    blocks,pair,d,diag=fixture()
    with pytest.raises(TemporalModelError,match="registered admission length"):
        call(blocks,pair,d,diag,length_m=.50)
    with pytest.raises(TemporalModelError,match="registered admission length"):
        call(blocks,pair,replace(d,registered_length_m=None),diag)
    with pytest.raises(TemporalModelError,match="registered admission length"):
        call(blocks,pair,replace(d,registered_length_m=float("nan")),diag)


def test_partial_candidate_has_identical_unknown_mask_through_export():
    blocks,pair,d,diag=fixture(partial=True)
    out=call(blocks,pair,d,diag)
    assert out.valid and len(out.fixed_labels)==4
    assert 9 not in out.retained_rows
    assert out.retained_rows==d.epochs[-1].rows_retained
    assert out.retained_rows==fixed_integer_gls(blocks[-1],pair[0].integers).rows_retained
    assert all(row in out.retained_rows for row in range(5))
    cb=fixed_integer_gls(blocks[-1],pair[0].integers).Cb
    assert cb[0,1]!=0


def test_fingerprint_canonical_numeric_layout_but_binds_frame():
    model=fixture()[0][0]
    expected=model_fingerprint(model)
    changed=replace(model,
        y=np.array(model.y,dtype=">f8"),A=np.asfortranarray(model.A),
        B=np.array(model.B,dtype=">f8"),Q=np.asfortranarray(model.Q),
        metadata={**model.metadata,"report_path":"/different/report","unrelated_note":"ignored"})
    assert model_fingerprint(changed)==expected
    assert model_fingerprint(replace(model,metadata={**model.metadata,"baseline_frame":"NED"}))!=expected
    assert model_fingerprint(replace(model,time_s=model.time_s+.2))!=expected


def test_record_binds_original_model_even_if_caller_mutates_array_after_observe():
    blocks,pair,d,diag=fixture()
    old=d.epochs[-1].model_fingerprint
    blocks[-1].y[0]+=.01
    assert old!=model_fingerprint(blocks[-1])
    with pytest.raises(TemporalModelError,match="current model differs"):
        call(blocks,pair,d,diag)
