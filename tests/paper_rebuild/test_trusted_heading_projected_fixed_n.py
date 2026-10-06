"""Small independent SD-generation oracles; no raw, references or CILS."""
import importlib.util,json,sys
from pathlib import Path
from dataclasses import replace
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts/paper_rebuild/carrier_phase"))
spec=importlib.util.spec_from_file_location("projected_fixed_n_runner",ROOT/"scripts/paper_rebuild/carrier_phase/trusted_heading_projected_fixed_n.py")
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
from legsa_gins.paper_rebuild.carrier_phase.arc_relations import SdArcNode,DdArcRelation,FrozenIntegerGraph
from legsa_gins.paper_rebuild.carrier_phase.arc_projection import transport_epoch
from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate
from legsa_gins.paper_rebuild.carrier_phase.multignss import MultiGnssEpoch,GroupDD,raw,signal_spec
from legsa_gins.paper_rebuild.carrier_phase.faults import stack_phase_fault_maps

def node(sv,arc=1):
    sig=f"0:{sv}:0:0"
    return SdArcNode(sig,json.dumps([f"1|{sig}|arc={arc}",f"2|{sig}|arc={arc}"],separators=(",",":")))

def sd_fixture(phase_bias=0.):
    oldpivot=node(1);nodes=[node(s) for s in range(2,9)]
    n=np.array([12,9,15,13,8,19,99])
    labels=tuple(DdArcRelation(x,oldpivot).label for x in nodes[:-1])
    integers=dict(zip(labels,(n[:-1]-10).tolist()))
    primary=FrozenCandidate.from_mapping("primary",10.,integers,labels,"synthetic-known-N")
    wrong=dict(integers);wrong[labels[0]]+=1
    competitor=FrozenCandidate.from_mapping("competitor",10.,wrong,labels,"synthetic-known-N")
    wave=signal_spec(raw.SignalIdentity(0,1,0,0)).wavelength_m
    g=np.array([[.2,.1,.7],[.4,-.5,.6],[-.7,.2,.1],[.3,.8,-.4],[-.4,-.4,.8],[.6,.3,-.2],[.1,-.9,-.3]])
    D=np.c_[np.eye(6),-np.ones(6)];dd=np.kron(np.eye(2),D)
    f=np.diag([.8]*7+[.01]*7);f[9,0]=.002;f[11,8]=.003
    qsd=f@f.T;models=[];events={};truth=[];direct=[]
    for k in range(5):
        t=10.+.2*(k+1);angle=.25*k
        baseline=.35*np.array([.9*np.cos(angle),.9*np.sin(angle),np.sqrt(.19)])
        geometry=g.copy();geometry[:,0]+=.01*k*np.arange(7)
        noise=np.zeros(14);noise[8]=wave*phase_bias
        ysd=np.r_[geometry@baseline,geometry@baseline+wave*n]+noise
        y=dd@ysd;B=dd@np.vstack([geometry,geometry]);Q=dd@qsd@dd.T
        A=np.vstack([np.zeros((6,6)),wave*np.eye(6)])
        ddlabels=tuple(DdArcRelation(x,nodes[-1]).label for x in nodes[:-1])
        pivot=raw.SignalIdentity(0,8,0,0);sats=tuple(raw.SignalIdentity(0,s,0,0) for s in range(2,8))
        group=GroupDD((0,0,0),pivot,sats,y,A,B,Q,ddlabels,tuple(range(12)),tuple(range(6)))
        models.append(MultiGnssEpoch(t,y,A,B,Q,ddlabels,(group,),dict(
            arc_label_policy="EXPLICIT_SD_ARCS",baseline_frame="ECEF",
            receiver_order="GNSS2_MINUS_GNSS1",dd_sign="SATELLITE_MINUS_PIVOT")))
        for item in nodes:
            for rx,token in enumerate(json.loads(item.arc),1):
                events[t,rx,item.signal]=dict(eligible=True,temporal_link_qualified=True,arc_token=token,reasons=[])
        truth.append(baseline);direct.append((ysd,qsd,geometry,n,dd,noise))
    return (primary,competitor),models,events,np.array(truth),nodes,direct

def projected_fixture():
    pair,models,events,truth,nodes,direct=sd_fixture(.25)
    graph=FrozenIntegerGraph.from_candidate(pair[0]).advance(nodes,time_s=models[0].time_s)
    return pair,models,graph,truth,nodes,direct

def test_u_y_b_q_f_match_independent_sd_differences_and_pivot_cancels():
    pair,models,graph,truth,nodes,direct=projected_fixture()
    model=models[0];view=transport_epoch(model,graph)
    ysd,qsd,g,n,dd,noise=direct[0]
    phase=np.zeros((5,7));phase[:,0]=-1.;phase[np.arange(5),np.arange(1,6)]=1.
    SD=np.zeros((11,14));SD[:6]=dd[:6];SD[6:,7:]=phase
    np.testing.assert_allclose(view.model.y,SD@ysd,atol=3e-15)
    np.testing.assert_allclose(view.model.B,SD@np.vstack([g,g]),atol=2e-15)
    np.testing.assert_allclose(view.model.Q,SD@qsd@SD.T,atol=2e-15)
    fmap=runner.transport_fault_map(model,view)
    wave=signal_spec(raw.SignalIdentity(0,1,0,0)).wavelength_m
    for j,h in enumerate(fmap.hypotheses):
        f=np.zeros(14);f[7+h.signal.sv_id-2]=wave
        np.testing.assert_allclose(fmap.matrix[:,j],SD@f,atol=1e-15)
    j=next(i for i,h in enumerate(fmap.hypotheses) if h.signal.sv_id==8)
    assert np.count_nonzero(fmap.matrix[:,j])==0

def test_gls_matches_explicit_full_q_and_zero_fault_column_has_no_finite_mdb():
    pair,models,graph,truth,nodes,direct=projected_fixture()
    view=transport_epoch(models[0],graph);fmap=runner.transport_fault_map(models[0],view)
    integers=dict(view.relation_projection.integer_items);m=view.model
    target=m.y-m.A@np.array([integers[x] for x in m.ambiguity_labels])
    qinv=np.linalg.inv(m.Q);cb=np.linalg.inv(m.B.T@qinv@m.B)
    baseline=cb@m.B.T@qinv@target;r=target-m.B@baseline
    d=runner.fixed_diagnostic(m,integers,fmap,runner.counts(),epoch_count=1)
    np.testing.assert_allclose(d["bhat"],baseline,atol=1e-11)
    np.testing.assert_allclose(d["Cb"],cb,atol=1e-11)
    assert d["residual_cost"]==pytest.approx(r@qinv@r,rel=1e-10)
    h=next(x for x in d["sensitivity"]["scores"] if x["key"]=="sd:0:8:0:0")
    assert h["mdb_cycles"] is None and h["detectable_amplitude_unbounded"]
    assert not d["accepted_integer_measurement"]

def test_dynamic_five_epoch_joint_matches_slot_sum_without_static_baseline():
    pair,models,events,truth,nodes,direct=sd_fixture()
    counts=runner.counts();result=runner.diagnose_window(pair,models,events,counts)
    assert result["status"]=="DIAGNOSTIC_COMPLETE"
    assert counts["fixed_n_gls_attempts"]==12 and counts["sphere_calls"]==10
    assert counts["cils_calls"]==counts["admission_calls"]==0
    np.testing.assert_allclose(np.array(result["joint"][0]["bhat"]).reshape(5,3),truth,atol=1e-11)
    assert np.linalg.norm(truth[0]-truth[-1])>.1
    assert result["joint"][0]["slot_sum_residual_identity_error"]<1e-10
    assert result["projection_merged_slots"]==0
    assert result["false_fix_probability"] is None

def test_retired_target_cannot_return_and_projection_merge_is_not_acceptance():
    pair,models,events,truth,nodes,direct=sd_fixture()
    # Both differ solely on G02; remove G02 immediately, then apparently restore it.
    events[models[0].time_s,1,nodes[0].signal]["temporal_link_qualified"]=False
    events[models[0].time_s,1,nodes[0].signal]["reasons"]=["TDCP_DOPPLER_INCONSISTENT"]
    result=runner.diagnose_window(pair,models,events,runner.counts())
    assert result["all_five_projections_merged"]
    assert all(s["phase_rows"]==4 for s in result["slots"])
    assert not result["accepted_integer_measurement"] and not result["all_alternatives_covered"]
    assert all(not any('"0:2:0:0"' in lab for lab,_ in s["projections"][0]["integer_items"]) for s in result["slots"])

def test_joint_persistent_fault_does_not_merge_new_sd_arc():
    pair,models,graph,truth,nodes,direct=projected_fixture()
    view=transport_epoch(models[0],graph);m=runner.transport_fault_map(models[0],view)
    altered=replace(m,hypotheses=tuple(replace(h,sd_arc_token=h.sd_arc_token+"new") for h in m.hypotheses))
    same=stack_phase_fault_maps((m,m),persistent=True)
    changed=stack_phase_fault_maps((m,altered),persistent=True)
    assert len(changed.hypotheses)==2*len(same.hypotheses)
    np.testing.assert_allclose(changed.matrix[:len(m.matrix),len(m.hypotheses):],0)
    np.testing.assert_allclose(changed.matrix[len(m.matrix):,:len(m.hypotheses)],0)

def test_late_shifted_future_rejected_without_fitting():
    pair,models,events,truth,nodes,direct=sd_fixture()
    bad=[replace(m,time_s=m.time_s+.2) for m in models];counts=runner.counts()
    with pytest.raises(ValueError,match="slots"):
        runner.diagnose_window(pair,bad,events,counts)
    assert counts["fixed_n_gls_attempts"]==0

def test_frozen_candidate_restore_rejects_wrong_source_and_integer():
    pair,models,events,truth,nodes,direct=sd_fixture()
    labels=pair[0].active_labels;times=[9.2+.2*i for i in range(10)]
    times[4]=10.
    source="SELECTED_OBSERVATION_MARGINAL_Q_V1:plan:case"
    pair=tuple(replace(c,candidate_id="partial_"+side,source_id=source) for c,side in zip(pair,("primary","competitor")))
    case=dict(case_id="case",selected_likelihood_plan_fingerprint="plan",
        subset_selection=dict(selected_labels=list(labels),selection_times=times[:5],selected_at=10.,status="READY"),
        frozen_candidates=[runner.serial(c) for c in pair],
        search=dict(certificate=dict(global_optimum_certified=True),all_labels=list(labels),
                    best=dict(ambiguity=[pair[0].integers[x] for x in labels]),
                    second=dict(ambiguity=[pair[1].integers[x] for x in labels])),
        admission=dict(primary_fingerprint=pair[0].fingerprint,competitor_fingerprint=pair[1].fingerprint))
    assert runner.restore_pair(case,times)==pair
    case["frozen_candidates"][0]["integer_items"][0][1]+=1
    with pytest.raises(ValueError,match="values/fingerprint"):
        runner.restore_pair(case,times)
