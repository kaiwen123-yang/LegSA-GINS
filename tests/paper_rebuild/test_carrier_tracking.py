"""Moving-baseline truth and terminal tracking regressions; no CILS/reference."""
from dataclasses import replace
import json,math
from tracking_oracle_fixture import generate_oracle_payload
import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate,AdmissionConfig,CausalAdmissionSession
from legsa_gins.paper_rebuild.carrier_phase.multignss import MultiGnssEpoch,GroupDD,SignalIdentity
from legsa_gins.paper_rebuild.carrier_phase.temporal import TemporalModelError,model_fingerprint
from legsa_gins.paper_rebuild.carrier_phase.measurement import (diagnose_validated_window,
    qualify_current_baseline,qualify_tracking_baseline)
from legsa_gins.paper_rebuild.carrier_phase.tracking import FixedCandidateTrack,TrackingConfig

L=.35
W=299792458./1575.42e6


def native_model(k,y,a,b,q,n):
    m=len(n);pivot=SignalIdentity(0,1,0,0);targets=tuple(SignalIdentity(0,i+2,0,0) for i in range(m))
    labels=tuple(json.dumps([f"0:{i+2}:0:0",f"target-{i}","0:1:0:0","pivot"],separators=(",",":")) for i in range(m))
    group=GroupDD((0,0,0),pivot,targets,y,a,b,q,labels,tuple(range(2*m)),tuple(range(m)))
    return MultiGnssEpoch((k+1)*.2,y,a,b,q,labels,(group,),{
        "baseline_frame":"ECEF","receiver_order":"GNSS2_MINUS_GNSS1","arc_label_policy":"EXPLICIT_SD_ARCS"})


def moving_models():
    # Construct raw single differences first, then physical DD and full Q.
    units=np.array([[.2,.3,.9],[.8,.1,.5],[-.4,.6,.7],[.1,-.8,.6],[-.8,-.1,.5],[.5,.6,.3]])
    units/=np.linalg.norm(units,axis=1)[:,None]
    nsd=np.array([3,9,-2,12,1,7]);d=np.column_stack((-np.ones(5),np.eye(5)))
    transform=np.block([[d,np.zeros_like(d)],[np.zeros_like(d),d]])
    q=transform@np.diag(np.r_[np.ones(6),np.full(6,.002**2)])@transform.T
    n=(d@nsd).astype(int);models=[];truth=[]
    for k in range(10):
        yaw=.12*k;tilt=.2*np.sin(.2*k)
        baseline=L*np.array([np.cos(yaw)*np.cos(tilt),np.sin(yaw)*np.cos(tilt),np.sin(tilt)])
        angle=.00004*k;c,s=np.cos(angle),np.sin(angle)
        u=units@np.array([[c,-s,0.],[s,c,0.],[0.,0.,1.]]).T
        y=np.r_[d@(-u@baseline+15.),d@(-u@baseline+W*nsd+39.)]
        a=np.vstack((np.zeros((5,5)),W*np.eye(5)));b=np.vstack((-d@u,-d@u))
        models.append(native_model(k,y,a,b,q.copy(),n));truth.append(baseline)
    return models,n,truth


def origin(models,n):
    labels=models[0].ambiguity_labels
    pair=tuple(FrozenCandidate.from_mapping(name,0.,dict(zip(labels,map(int,values))),labels,"truth-fixture")
        for name,values in (("primary",n),("competitor",n+np.r_[1,np.zeros(len(n)-1,dtype=int)])))
    config=AdmissionConfig();policy=TrackingConfig()
    session=CausalAdmissionSession(*pair,config)
    for m in models[:5]:session.observe(m)
    admission=session.finalize()
    diagnosis=diagnose_validated_window(models[:5],pair[0],admission,family_alpha=policy.fault_family_alpha)
    measurement=qualify_current_baseline(models[4],pair[0],admission,diagnosis,
        length_m=L,angular_floor_rad=policy.angular_floor_rad,availability_time_s=models[4].time_s)
    return pair,admission,diagnosis,measurement,config,policy


def start(models,n,**overrides):
    pair,admission,diagnosis,measurement,config,policy=origin(models,n)
    params=dict(primary=pair[0],competitor=pair[1],origin_models=models[:5],origin_admission=admission,
        origin_diagnosis=diagnosis,origin_measurement=measurement,admission_config=config,tracking_config=policy)
    params.update(overrides)
    return FixedCandidateTrack.start(**params)


def test_true_fixed_N_tracks_current_rotating_baseline_and_full_covariance():
    models,n,truth=moving_models();track=start(models,n);first_fp=track.primary.fingerprint
    assert track.last_accepted_time_s==models[4].time_s
    receipts=[]
    for k in range(5,10):
        step=track.observe(models[k],availability_time_s=models[k].time_s)
        assert not step.terminal and step.measurement.valid,step.status
        np.testing.assert_allclose(step.measurement.baseline_ecef_m,truth[k],atol=1e-10)
        q=models[k].Q;b=models[k].B
        cb=np.linalg.solve(b.T@np.linalg.solve(q,b),np.eye(3))
        np.testing.assert_allclose(step.measurement.covariance_ecef_m2,
            cb+np.eye(3)*(L*math.radians(1.5))**2,rtol=1e-10,atol=1e-15)
        assert step.receipt.origin_selected_at==0 and track.primary.fingerprint==first_fp
        assert step.receipt.observed_times==tuple(m.time_s for m in models[k-4:k+1])
        assert step.receipt.false_fix_probability is None and not step.receipt.independent_repeated_acceptances
        assert step.measurement.measurement_time==models[k].time_s
        receipts.append(step.receipt)
    assert receipts[1].ordered_model_fingerprints[:-1]==receipts[0].ordered_model_fingerprints[1:]
    assert receipts[1].previous_receipt_fingerprint==receipts[0].fingerprint
    assert track.state=="ACTIVE" and track.primary.integers==dict(zip(models[0].ambiguity_labels,n))


@pytest.mark.parametrize("kind",["primary","competitor","selected_at","source","origin_y","alpha","interval","window","length","diagnostic_alpha","floor"])
def test_origin_binding_and_policy_are_recomputed_not_trusted_booleans(kind):
    models,n,_=moving_models();pair,d,diag,measurement,config,policy=origin(models,n)
    kwargs={}
    if kind=="primary":kwargs["primary"]=replace(pair[0],integer_items=pair[1].integer_items)
    if kind=="competitor":kwargs["competitor"]=replace(pair[1],integer_items=pair[0].integer_items)
    if kind=="selected_at":kwargs["primary"]=replace(pair[0],selected_at=.2)
    if kind=="source":kwargs["primary"]=replace(pair[0],source_id="different")
    if kind=="origin_y":
        changed=list(models[:5]);changed[0]=replace(changed[0],y=changed[0].y+.02)
        kwargs["origin_models"]=changed
    if kind=="alpha":kwargs["admission_config"]=replace(config,alpha_total=.02)
    if kind=="interval":kwargs["admission_config"]=replace(config,epoch_interval_s=.21)
    if kind=="window":kwargs["admission_config"]=replace(config,validation_epochs=4)
    if kind=="length":kwargs["admission_config"]=replace(config,length_m=.36)
    if kind=="diagnostic_alpha":kwargs["tracking_config"]=replace(policy,fault_family_alpha=.02)
    if kind=="floor":kwargs["tracking_config"]=replace(policy,angular_floor_rad=.03)
    with pytest.raises(TemporalModelError):start(models,n,**kwargs)


@pytest.mark.parametrize("kind",["target_slip","pivot_slip","arc_reset","half_cycle_invalid","gap","late_availability","duplicate","length"])
def test_first_failure_is_terminal_even_if_clean_labels_return(kind):
    models,n,_=moving_models();track=start(models,n);m=models[5]
    if kind=="gap":step=track.missing(m.time_s,"MISSING_RAW_EPOCH")
    elif kind=="half_cycle_invalid":step=track.missing(m.time_s,"SELECTED_PHASE_HALF_CYCLE_UNRESOLVED")
    else:
        if kind in ("target_slip","pivot_slip"):
            y=m.y.copy()
            if kind=="target_slip":y[5]+=W
            else:y[5:]-=W
            m=replace(m,y=y)
        if kind=="arc_reset":m=replace(m,ambiguity_labels=("new target arc",*m.ambiguity_labels[1:]))
        if kind=="duplicate":m=models[4]
        if kind=="length":m=replace(m,y=m.y+m.B@np.asarray(moving_models()[2][5]))
        available=m.time_s+.2 if kind=="late_availability" else m.time_s
        step=track.observe(m,availability_time_s=available)
    assert step.terminal and not step.measurement.valid,step.status
    assert track.state=="RELEASED" and track.last_accepted_time_s==models[4].time_s
    with pytest.raises(TemporalModelError,match="cannot resume"):
        track.observe(models[6],availability_time_s=models[6].time_s)
    with pytest.raises(TemporalModelError,match="cannot resume"):track.missing(models[6].time_s)


def test_old_window_receipt_cannot_export_new_or_backdated_model():
    models,n,_=moving_models();track=start(models,n)
    step=track.observe(models[5],availability_time_s=models[5].time_s)
    for model,t in ((models[6],models[6].time_s),(models[5],models[5].time_s-.2)):
        with pytest.raises(TemporalModelError):
            qualify_tracking_baseline(model,track.primary,step.receipt,binding=track.binding,availability_time_s=t)
    with pytest.raises(TemporalModelError):
        qualify_tracking_baseline(models[5],replace(track.primary,selected_at=.2),step.receipt,binding=track.binding,
                                  availability_time_s=models[5].time_s)
    changed=replace(step.receipt,admission_config=replace(step.receipt.admission_config,alpha_total=.02))
    with pytest.raises(TemporalModelError,match="origin/policy binding"):
        qualify_tracking_baseline(models[5],track.primary,changed,binding=track.binding,availability_time_s=models[5].time_s)


def test_original_arrays_are_copied_before_rolling_use():
    models,n,truth=moving_models();track=start(models,n)
    models[4].y[0]+=100
    step=track.observe(models[5],availability_time_s=models[5].time_s)
    assert step.measurement.valid
    np.testing.assert_allclose(step.measurement.baseline_ecef_m,truth[5],atol=1e-10)
    models[5].y[0]+=100
    later=track.observe(models[6],availability_time_s=models[6].time_s)
    assert later.measurement.valid


def test_time_tolerance_cannot_walk_away_from_original_grid():
    models,n,_=moving_models();track=start(models,n)
    m=replace(models[5],time_s=models[5].time_s+.009)
    assert track.observe(m,availability_time_s=m.time_s).measurement.valid
    m=replace(models[6],time_s=models[6].time_s+.018)
    assert track.observe(m,availability_time_s=m.time_s).terminal


def test_independent_SD_oracle_current_baselines():
    z=generate_oracle_payload()
    n=z["moving_00_N_true"].astype(int)
    models=[native_model(k,*[z[f"moving_{k:02d}_{f}"].copy() for f in ("y","A","B","Q")],n) for k in range(10)]
    track=start(models,n)
    for k in range(5,10):
        step=track.observe(models[k],availability_time_s=models[k].time_s)
        assert step.measurement.valid,step.status
        np.testing.assert_allclose(step.measurement.baseline_ecef_m,z[f"moving_{k:02d}_b_true"],atol=1e-10)
    # Independent counterexample: wrong primary and true competitor both fit.
    n=z["alias_00_N_true"].astype(int);wrong=z["alias_00_N_wrong"].astype(int)
    models=[native_model(k,*[z[f"alias_{k:02d}_{f}"].copy() for f in ("y","A","B","Q")],n) for k in range(5)]
    labels=models[0].ambiguity_labels
    pair=tuple(FrozenCandidate.from_mapping(name,0.,dict(zip(labels,map(int,val))),labels,"alias-oracle")
               for name,val in (("wrong",wrong),("true",n)))
    session=CausalAdmissionSession(*pair,AdmissionConfig())
    for model in models:session.observe(model)
    decision=session.finalize()
    assert decision.primary.passes and decision.competitor.passes
    assert decision.status=="UNRESOLVED_COMPETITION"
    assert decision.false_fix_probability is None


def test_measurement_rejects_other_origin_and_forged_gate_summary():
    models,n,_=moving_models();track=start(models,n)
    step=track.observe(models[5],availability_time_s=models[5].time_s)
    wrong=replace(track.binding,origin_id="f"*64)
    with pytest.raises(TemporalModelError,match="origin/policy binding"):
        qualify_tracking_baseline(models[5],track.primary,step.receipt,binding=wrong,
                                  availability_time_s=models[5].time_s)
    forged=replace(step.receipt,primary=replace(step.receipt.primary,residual_cost=99.))
    with pytest.raises(TemporalModelError,match="gate summary"):
        qualify_tracking_baseline(models[5],track.primary,forged,binding=track.binding,
                                  availability_time_s=models[5].time_s)
