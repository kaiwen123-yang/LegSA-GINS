"""Eight bounded synthetic interface/physical checks; zero integer searches."""
from dataclasses import replace
import json,math
import numpy as np
import pytest
from test_carrier_candidate_lifecycle import origin,generated,node,AXES,BASE
from legsa_gins.paper_rebuild.carrier_phase.set_provider import (
    CompleteSetPointProvider,SetProviderPolicy,SetProviderCalls)
from legsa_gins.paper_rebuild.carrier_phase.candidate_lifecycle import LifecycleCalls
from legsa_gins.paper_rebuild.carrier_phase.temporal import TemporalModelError,model_fingerprint
from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import ConditionalBaseline

CALLS=SetProviderCalls(lifecycle=LifecycleCalls(gls_limit=180,glrt_limit=180),geometry_limit=180,sphere_limit=64)


def provider(source=None,available=10.,**policy):
    return CompleteSetPointProvider(origin() if source is None else source,
        source_available_at_s=available,policy=SetProviderPolicy(**policy))


def step(p,i,*,decision=None,nodes=None,model=None,**kwargs):
    t=10.+.2*i
    if model is None:model,_=generated(t,**kwargs)
    return p.advance(model,time_s=t,qualified_nodes=p.alive_nodes if nodes is None else nodes,
        horizontal_axes=AXES,decision_time_s=t if decision is None else decision,calls=CALLS)


def test_01_known_integer_moving_baseline_and_five_current_slots():
    p=provider();steps=[]
    for i in range(1,7):
        yaw=.5+.02*i;truth=.35*np.array([math.cos(yaw),math.sin(yaw),0.])
        r=step(p,i,baseline=truth);steps.append(r)
        if i<5:assert not r.measurement.valid
        else:
            assert r.measurement.valid
            np.testing.assert_allclose(r.measurement.baseline_ecef_m,truth,atol=1e-12)
            assert len(r.receipt.epochs)==5 and r.receipt.common_origin_fingerprints
            assert all(e.sphere_raw_cost<=e.expanded_raw_threshold for e in r.receipt.epochs)
            assert max(e.sphere_cost_identity_error for e in r.receipt.epochs)<1e-10
            assert not r.measurement.integer_truth_known and not r.measurement.production_validated
            assert r.measurement.calibrated_false_fix_probability is None
    assert steps[4].receipt.source_selected_at_s==10.
    assert steps[4].receipt.source_fingerprint==p.source.fingerprint
    assert len({e.original_model_fingerprint for e in steps[4].receipt.epochs})==5


def test_02_delayed_source_catchup_never_backdates():
    p=provider(available=11.2)
    with pytest.raises(TemporalModelError,match='availability'):step(p,1)
    for i in range(1,8):
        r=step(p,i,decision=11.4)
        if i<7:assert not r.measurement.valid
    assert r.measurement.valid and r.measurement.measurement_time==11.4
    assert r.receipt.source_selected_at_s==10. and r.receipt.source_available_at_s==11.2
    # A caller reporting actual finish after the observation cannot export it.
    delayed=step(p,8,decision=11.600001)
    assert not delayed.measurement.valid and delayed.status=='INTERNAL_CATCHUP_NOT_EXPORTED'


def test_03_temporary_bad_observation_resets_but_keeps_source():
    p=provider()
    for i in range(1,5):step(p,i)
    bad=step(p,5,phase_bias={3:8.})
    assert not bad.measurement.valid and bad.validation_streak==0 and len(p.lifecycle.graphs)==1
    for i in range(6,10):assert not step(p,i).measurement.valid
    assert step(p,10).measurement.valid
    assert p.source.selected_at==10. and len(p.lifecycle.graphs)==1


def test_04_multiple_classes_no_sphere_call_or_mean():
    n=origin().integers[0];other=(n[0]+1,*n[1:])
    p=provider(origin(vectors=[n,other]));before=CALLS.python_sphere_calls
    for i in range(1,6):
        r=step(p,i,scale=300.)
        assert r.domain.compatible_class_count==2 and len(r.domain.classes)==2
        assert not r.measurement.valid and r.validation_streak==0
    assert CALLS.python_sphere_calls==before


def test_05_alternating_single_origins_do_not_accumulate_streak():
    n=origin().integers[0];other=(n[0]+7,*n[1:])
    p=provider(origin(vectors=[n,other]))
    for i in range(1,7):
        r=step(p,i,phase_bias={2:7.} if i%2==0 else None)
        assert r.domain.compatible_class_count==1
        assert not r.measurement.valid and r.validation_streak==1
    assert len(p.lifecycle.graphs)==2  # no temporary-cost deletion


def test_06_retirement_new_token_and_terminal_no_resurrection():
    p=provider()
    for i in range(1,5):step(p,i)
    nodes=[node(s) for s in range(1,6)]+[node(6,'new')]
    for i in range(5,10):
        r=step(p,i,nodes=nodes,tokens={6:'new'},phase_bias={6:21.})
        assert r.domain.phase_rows==4
        assert all('new' not in label for c in r.domain.classes for label,_ in c.integer_items)
        assert r.measurement.valid==(i==9)
    loss=step(p,10,nodes=[node(1)])
    assert loss.status=='PHYSICAL_SOURCE_ENDED' and p.terminal
    recovered=step(p,11,nodes=[node(s) for s in range(1,7)])
    assert recovered.status=='SOURCE_TERMINAL_NO_RESURRECTION' and not recovered.measurement.valid


def test_07_actual_raw_cost_check_chronology_and_expiry(monkeypatch):
    import legsa_gins.paper_rebuild.carrier_phase.set_provider as mod
    # Deliberately return another same-length point. Independent raw residual
    # check must reject it even when the sphere routine reports zero objective.
    monkeypatch.setattr(mod,'constrained_baseline',lambda c,C,L:ConditionalBaseline(-BASE.copy(),0.,0.,0.,False))
    p=provider();r=step(p,1)
    assert r.status=='CURRENT_SPHERE_POINT_OUTSIDE_ORIGINAL_COST_DOMAIN' and r.validation_streak==0
    with pytest.raises(TemporalModelError,match='precedes'):step(p,2,decision=10.3)
    expired=provider(max_source_age_s=1.01)
    r=step(expired,1,decision=11.1)
    assert r.status=='SOURCE_EXPIRED' and expired.terminal
    assert not step(expired,2,decision=11.2).measurement.valid


def test_08_empty_incomplete_resource_cap_and_consumed_failure_streak():
    empty=provider(origin(vectors=[]));r=step(empty,1)
    assert r.domain.status=='EMPTY_SOURCE' and not r.measurement.valid
    with pytest.raises(TemporalModelError):origin(complete=False)
    n=origin().integers[0]
    with pytest.raises(TemporalModelError,match='cap'):
        provider(origin(vectors=[n,(n[0]+1,*n[1:])]),max_source_candidates=1)
    p=provider()
    for i in range(1,5):step(p,i)
    old_limit=CALLS.geometry_limit;CALLS.geometry_limit=CALLS.geometry_calls
    try:
        with pytest.raises(TemporalModelError,match='budget'):step(p,5)
    finally:CALLS.geometry_limit=old_limit
    r=step(p,6)
    assert not r.measurement.valid and r.validation_streak==1


@pytest.fixture(scope='module',autouse=True)
def call_receipt():
    yield
    print('SET_PROVIDER_LOCAL_CALLS '+json.dumps(dict(
        fixed_integer_GLS=CALLS.lifecycle.fixed_integer_gls_calls,GLRT=CALLS.lifecycle.single_fault_glrt_calls,
        geometry=CALLS.geometry_calls,python_sphere_ML=CALLS.python_sphere_calls,
        integer_enumeration=0,CILS=0,LAMBDA=0,native_navigation=0,real_model_reads=0,reference_reads=0)))
