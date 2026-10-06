"""Independent physical SD generation; no real files or integer searches."""
from dataclasses import replace
import json
import math
import numpy as np
import pytest
from scipy.stats import chi2
from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate
from legsa_gins.paper_rebuild.carrier_phase.arc_relations import SdArcNode,DdArcRelation
from legsa_gins.paper_rebuild.carrier_phase.candidate_lifecycle import (
    CompleteSourceSet,ConditionalCandidateSet,LifecycleConfig,LifecycleCalls,
    current_class_domain,transported_fault_map,classify_phase_effects)
from legsa_gins.paper_rebuild.carrier_phase.faults import (
    PhaseFaultMap,PhaseFaultHypothesis,fixed_integer_gls,single_fault_glrt)
from legsa_gins.paper_rebuild.carrier_phase.multignss import MultiGnssEpoch,GroupDD,raw,signal_spec
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock,TemporalModelError

BUDGETS=[]
EXTRA_GLS=0
EXTRA_GLRT=0
AXES=np.array([[1.,0.,0.],[0.,1.,0.]])
WAVE=signal_spec(raw.SignalIdentity(0,1,0,0)).wavelength_m
UNITS=np.array([[0.,0.,1.],[.8,0.,.6],[0.,.8,.6],[-.6,-.5,.62449979983984],
                [.4,-.8,.447213595499958],[-.8,.4,.447213595499958],[.2,.4,.894427190999916]])
UNITS=UNITS/np.linalg.norm(UNITS,axis=1)[:,None]
NSD=np.array([8,10,7,13,11,9,91])
BASE=np.array([.28,.21,0.])


def node(s,token='a'):
    return SdArcNode(f'0:{s}:0:0',token)


def origin(*,vectors=None,complete=True):
    labels=tuple(DdArcRelation(node(s),node(1)).label for s in range(2,7))
    n=tuple(int(x) for x in NSD[1:6]-NSD[0])
    return CompleteSourceSet('physical-source',10.,labels,(n,) if vectors is None else tuple(vectors),
                             'a'*64,complete,150.)


def budget():
    b=LifecycleCalls();BUDGETS.append(b);return b


def generated(t=10.2,*,pivot=1,baseline=BASE,phase_bias=None,noise=None,scale=1.,tokens=None):
    # Physical SD range is -u_s^T b; differences give registered u_p-u_s.
    sats=tuple(range(2,7));ids=(*sats,pivot);m=len(sats)
    idx=np.array(ids)-1;g=-UNITS[idx]
    sd=np.r_[g@baseline,g@baseline+WAVE*NSD[idx]]
    if phase_bias:
        for satellite,cycles in phase_bias.items():
            if satellite in ids:sd[m+1+ids.index(satellite)]+=WAVE*cycles
    factor=np.diag([.003*scale]*(m+1)+[.0003*scale]*(m+1))
    factor[m+2,0]=.00005*scale
    factor[m+3,m+1]=.00009*scale
    qs=factor@factor.T
    if noise is not None:sd=sd+noise
    d=np.c_[np.eye(m),-np.ones(m)];u=np.kron(np.eye(2),d)
    y=u@sd;b=u@np.vstack((g,g));q=u@qs@u.T
    a=np.vstack((np.zeros((m,m)),WAVE*np.eye(m)))
    tokens=tokens or {};pivotnode=node(pivot,tokens.get(pivot,'a'))
    labels=tuple(DdArcRelation(node(s,tokens.get(s,'a')),pivotnode).label for s in sats)
    identities=tuple(raw.SignalIdentity(0,s,0,0) for s in sats)
    group=GroupDD((0,0,0),raw.SignalIdentity(0,pivot,0,0),identities,y,a,b,q,labels,tuple(range(2*m)),tuple(range(m)))
    model=MultiGnssEpoch(t,y,a,b,q,labels,(group,),dict(baseline_frame='ECEF',receiver_order='GNSS2_MINUS_GNSS1',dd_sign='SATELLITE_MINUS_PIVOT',arc_label_policy='EXPLICIT_SD_ARCS'))
    return model,dict(sd=sd,qsd=qs,G=g,original_U=u,ids=ids)


def advance(track,model,*,nodes=None,b=None):
    return track.advance(model,time_s=model.time_s,qualified_nodes=track.alive_nodes if nodes is None else nodes,
                         horizontal_axes=AXES,calls=budget() if b is None else b)


def contains(arc,angle):
    return ((angle-arc.start_rad)%(2*math.pi))<=arc.width_rad+1e-12


def test_01_clean_physical_truth_full_covariance_domain():
    track=ConditionalCandidateSet(origin());model,_=generated();result=advance(track,model)
    assert result.status=='CURRENT_SET_SINGLE' and result.direction_domain_qualified
    c=result.classes[0]
    np.testing.assert_allclose(c.baseline_center_m,BASE,atol=2e-13)
    w=np.linalg.inv(model.Q);expected=np.linalg.inv(model.B.T@w@model.B)
    np.testing.assert_allclose(c.baseline_covariance_m2,expected,rtol=1e-12,atol=1e-18)
    assert contains(result.azimuth_outer_arc,math.atan2(BASE[1],BASE[0]))
    assert not result.accepted_integer_measurement and result.false_fix_probability is None


def test_02_bad_observation_is_temporary_not_integer_deletion():
    track=ConditionalCandidateSet(origin());model,_=generated(phase_bias={3:8.})
    first=advance(track,model);fingerprints=tuple(g.origin_fingerprint for g in track.graphs)
    assert not first.direction_domain_qualified and not track.physically_ended
    clean,_=generated(10.4);second=advance(track,clean)
    assert second.direction_domain_qualified
    assert tuple(g.origin_fingerprint for g in track.graphs)==fingerprints


def test_03_retired_tokens_never_resurrect_even_identical_measurements():
    track=ConditionalCandidateSet(origin());model,_=generated()
    result=advance(track,model,nodes=[node(1)])
    assert result.physically_ended
    later,_=generated(10.4);again=advance(track,later,nodes=[node(s) for s in range(1,7)])
    assert again.status=='PHYSICAL_SOURCE_ENDED' and not again.classes


def test_04_unknown_new_pivot_noise_and_integer_cancel_full_Q_kept():
    track=ConditionalCandidateSet(origin());model,physical=generated(pivot=7,phase_bias={7:2.})
    result=advance(track,model,nodes=[node(s) for s in range(2,7)])
    assert result.phase_rows==4 and result.phase_rank==3
    current=track.graphs[0]
    from legsa_gins.paper_rebuild.carrier_phase.arc_projection import transport_epoch
    view=transport_epoch(model,current)
    # Direct SD map: all original code, phase targets 3..6 minus surviving G02.
    direct=np.zeros((9,12));direct[:5]=physical['original_U'][:5]
    for j in range(4):direct[5+j,6]=-1.;direct[5+j,7+j]=1.
    np.testing.assert_allclose(view.model.Q,direct@physical['qsd']@direct.T,atol=1e-19)
    np.testing.assert_allclose(view.model.y,direct@physical['sd'],atol=1e-14)
    np.testing.assert_allclose(result.classes[0].baseline_center_m,BASE,atol=2e-13)
    zero=[e for e in result.classes[0].phase_effects if e.key.endswith('0:7:0:0')]
    assert len(zero)==1 and zero[0].classification=='NA_NO_CURRENT_EFFECT'
    assert result.direction_domain_qualified


def test_05_exact_projection_merge_preserves_both_origins():
    n=origin().integers[0]
    source=origin(vectors=[n,tuple(x+4 for x in n)])
    track=ConditionalCandidateSet(source);model,_=generated(pivot=7)
    result=advance(track,model,nodes=(node(s) for s in range(2,7)))
    assert len(result.classes)==1 and len(result.classes[0].origins)==2
    assert result.source_origin_count==2 and not result.search_certificate_transferred
    assert not result.all_global_current_alternatives_covered


def test_06_incomplete_and_duplicate_source_fail_closed():
    with pytest.raises(TemporalModelError,match='complete'):origin(complete=False)
    n=origin().integers[0]
    with pytest.raises(TemporalModelError):origin(vectors=[n,n])
    with pytest.raises(TemporalModelError,match='length'):
        ConditionalCandidateSet(origin(),LifecycleConfig(length_m=.4))
    source=origin();labels=source.labels
    saved={'raw_envelope':{'numerical_support_complete':True,'problem_fingerprint':'a'*64,
        'status':'COMPLETE_RELAXED_SUPPORT','candidates':[{'integer':list(n)}],
        'ambiguity_labels':labels,'target_time_s':10.,'raw_cost_threshold':150.},
        'length_necessary_support':{'raw_support_complete':True,'necessary_support_complete':True,
        'problem_fingerprint':'a'*64,'retained_candidates':[{'integer':list(n)}],
        'items':[{'integer':list(n),'retained':True}],'raw_observed_candidates':1},
        'selection':{'selected_labels':labels,'selected_at':10.}}
    restored=CompleteSourceSet.from_saved_record(saved,source_id='test-saved',registered_length_m=.35)
    assert restored.integers==(n,) and restored.length_m==.35
    saved['length_necessary_support']['problem_fingerprint']='b'*64
    with pytest.raises(TemporalModelError,match='fingerprint'):
        CompleteSourceSet.from_saved_record(saved,source_id='test-saved',registered_length_m=.35)


def test_07_signed_alias_is_not_quality_veto():
    track=ConditionalCandidateSet(origin());model,_=generated()
    from legsa_gins.paper_rebuild.carrier_phase.arc_projection import transport_epoch
    graph=track.graphs[0].advance(track.alive_nodes,time_s=model.time_s);view=transport_epoch(model,graph)
    _,fmap=transported_fault_map(model,view)
    alias=replace(fmap.hypotheses[0],key='receiver_reverse_alias')
    fmap=PhaseFaultMap(np.c_[fmap.matrix,-fmap.matrix[:,0]],(*fmap.hypotheses,alias),fmap.row_indices,fmap.original_row_count)
    d=current_class_domain(view.model,dict(view.relation_projection.integer_items),('source',),fmap,
                           AXES,LifecycleConfig(),budget(),phase_rows=5,phase_rank=3)
    assert any(e.classification=='OBSERVABLE_ALIAS' for e in d.phase_effects)
    assert not d.quality_reasons


def test_08_unobservable_baseline_effect_distinct_from_exact_zero():
    global EXTRA_GLS,EXTRA_GLRT
    b=np.array([[1.,0,0],[0,1.,0],[0,0,1.],[1.,1.,1.]])
    model=EpochBlock(1.,b@BASE,np.empty((4,0)),b,np.eye(4),(),{'baseline_frame':'ECEF'})
    EXTRA_GLS+=1;fit=fixed_integer_gls(model,{})
    h=PhaseFaultHypothesis('physical_common_direction',raw.SignalIdentity(0,2,0,0),(0,0,0),None,None,'sd',WAVE,())
    fmap=PhaseFaultMap(np.c_[b@np.array([.1,.2,-.1]),np.zeros(4)],(h,replace(h,key='cancelled')),tuple(range(4)),4)
    EXTRA_GLRT+=1;diag=single_fault_glrt(fit,fmap)
    effects=classify_phase_effects(fit,fmap,diag)
    assert effects[0].classification=='DANGEROUS_UNOBSERVABLE_BASELINE_EFFECT'
    np.testing.assert_allclose(effects[0].baseline_gain_m_per_cycle,[.1,.2,-.1],atol=1e-14)
    assert effects[1].classification=='NA_NO_CURRENT_EFFECT'


def test_09_true_scalar_phase_bias_significant_class_stays_in_union():
    # Choose a physical target bias using an independent dense residual projector.
    template_model,_=generated();f=np.zeros(10);f[6]=WAVE
    w=np.linalg.inv(template_model.Q);b=template_model.B
    cb=np.linalg.inv(b.T@w@b);gain=cb@b.T@w@f
    information=float(f@w@f-(b.T@w@f)@cb@(b.T@w@f))
    amplitude=math.sqrt(.8*chi2.ppf(.99,10)/information)
    baseline=np.cross(gain,[0.,0.,1.]);baseline=.35*baseline/np.linalg.norm(baseline)
    model,_=generated(baseline=baseline,phase_bias={3:amplitude})
    track=ConditionalCandidateSet(origin());result=advance(track,model)
    assert result.compatible_class_count==1
    assert 'PHASE_GLRT_SIGNIFICANT' in result.classes[0].quality_reasons
    assert result.azimuth_outer_arc is not None and not result.direction_domain_qualified
    assert len(track.graphs)==1


def test_10_unknown_new_arc_phase_is_not_given_old_N():
    track=ConditionalCandidateSet(origin());model,_=generated(tokens={6:'new'},phase_bias={6:21.})
    result=advance(track,model,nodes=[node(s) for s in range(1,6)]+[node(6,'new')])
    assert result.phase_rows==4
    assert all('new' not in label and '0:6:0:0' not in label for label,_ in result.classes[0].integer_items)
    assert result.direction_domain_qualified


def test_11_continuous_domain_wrap_is_not_center_point(monkeypatch):
    baseline=np.array([-.35,0.,0.]);model,_=generated(baseline=baseline,scale=20.)
    result=advance(ConditionalCandidateSet(origin()),model)
    arc=result.azimuth_outer_arc
    assert arc.width_rad>0 and contains(arc,math.pi-.001) and contains(arc,-math.pi+.001)
    original=np.linalg.eigvalsh
    monkeypatch.setattr(np.linalg,'eigvalsh',lambda value: np.array([-2.,-1.])
                        if value.shape==(2,2) else original(value))
    with pytest.raises(TemporalModelError,match='horizontal Cb'):
        advance(ConditionalCandidateSet(origin()),model)


def test_12_near_vertical_full_circle_not_fake_heading():
    model,_=generated(baseline=np.array([0.,0.,.35]))
    result=advance(ConditionalCandidateSet(origin()),model)
    assert result.azimuth_outer_arc.full_circle


def test_13_missing_model_does_not_delete_continuous_source():
    track=ConditionalCandidateSet(origin());calls=budget()
    missing=track.advance(None,time_s=10.2,qualified_nodes=track.alive_nodes,horizontal_axes=AXES,calls=calls)
    assert missing.status=='CURRENT_MODEL_UNAVAILABLE' and calls.fixed_integer_gls_calls==0
    model,_=generated(10.4);assert advance(track,model,b=calls).direction_domain_qualified


def test_14_empty_source_and_budget_exhaustion_never_publish():
    track=ConditionalCandidateSet(origin(vectors=[]));model,_=generated();calls=budget()
    result=advance(track,model,b=calls)
    assert result.status=='EMPTY_SOURCE' and calls.fixed_integer_gls_calls==0
    calls=LifecycleCalls(gls_limit=0);BUDGETS.append(calls)
    with pytest.raises(TemporalModelError,match='budget'):
        advance(ConditionalCandidateSet(origin()),model,b=calls)


def test_15_fixed_slot_and_frame_identity_fail_closed():
    track=ConditionalCandidateSet(origin());model,_=generated(10.4)
    with pytest.raises(TemporalModelError,match='slot'):advance(track,model)
    model,_=generated();model=replace(model,metadata={**model.metadata,'baseline_frame':'NED'})
    # transport preserves declared ECEF semantics only for registered input metadata.
    with pytest.raises(TemporalModelError):advance(track,model)
    model,_=generated();extreme=model.y.copy();extreme[0]=1e308
    with np.errstate(over='ignore',invalid='ignore'):
        with pytest.raises(TemporalModelError,match='nonfinite'):
            advance(ConditionalCandidateSet(origin()),replace(model,y=extreme))


@pytest.fixture(scope="module",autouse=True)
def local_call_receipt():
    yield
    print('CANDIDATE_LIFECYCLE_LOCAL_RECEIPT '+json.dumps(dict(
        module_fixed_integer_GLS_calls=sum(b.fixed_integer_gls_calls for b in BUDGETS),
        module_GLRT_calls=sum(b.single_fault_glrt_calls for b in BUDGETS),
        explicit_auxiliary_fixed_GLS_calls=EXTRA_GLS,explicit_auxiliary_GLRT_calls=EXTRA_GLRT,
        enumeration_calls=0,CILS_calls=0,native_navigation_calls=0,real_model_reads=0,reference_reads=0)))


def test_16_all_original_classes_retained_despite_current_cost_rejection():
    n=origin().integers[0];other=(n[0]+7,*n[1:])
    track=ConditionalCandidateSet(origin(vectors=[n,other]));model,_=generated()
    result=advance(track,model)
    assert len(result.classes)==2 and result.compatible_class_count==1
    assert len(track.graphs)==2 and not track.physically_ended
    np.testing.assert_allclose(result.classes[0].baseline_covariance_m2,
                               result.classes[1].baseline_covariance_m2,rtol=0,atol=0)
