"""Independent matrix, likelihood and tiny known-integer checks; synthetic only."""
from dataclasses import replace
import itertools
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import brentq

from legsa_gins.paper_rebuild.carrier_phase import selected_likelihood as selected
from legsa_gins.paper_rebuild.carrier_phase.partial import PartialPolicy, preselect_partial_labels
from legsa_gins.paper_rebuild.carrier_phase.multignss import GroupDD, MultiGnssEpoch, SignalIdentity, signal_spec
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock, TemporalModelError, assemble_epochs


def identity(s):
    return ':'.join(map(str,(s.gnss_id,s.sv_id,s.sig_id,s.freq_id)))


def fixture_models(m=9, count=5):
    h=np.array([[.5,-.8,.2],[-.7,-.3,.4],[.2,.6,-.8],[.8,.4,.5],[-.4,.2,.7],
                [.1,-.5,-.6],[.3,.7,.2],[-.6,.2,-.5],[.4,-.1,.8]])[:m]
    keys=[((0,0,0),range(m))] if m!=9 else [((0,0,0),range(3)),((0,3,0),range(3,6)),((2,0,0),range(6,9))]
    c=np.eye(m)+.1*np.ones((m,m))
    a=np.zeros((2*m,m)); labels=[]; descriptions=[]
    for key, indices in keys:
        indices=tuple(indices); pivot=SignalIdentity(key[0],1,key[1],key[2])
        targets=tuple(SignalIdentity(key[0],2+i,key[1],key[2]) for i in range(len(indices)))
        c[np.ix_(indices,indices)]+=1. # shared pivot term; additional cross-group covariance above
        for column,target in zip(indices,targets):
            labels.append(json.dumps([identity(target),'target-arc',identity(pivot),'pivot-arc'],separators=(',',':')))
            a[m+column,column]=signal_spec(target).wavelength_m
        descriptions.append((key,pivot,targets,indices+tuple(m+i for i in indices),indices))
    code=np.linspace(.02,.035,m); phase=np.linspace(.002,.003,m)
    q=np.block([[code[:,None]*c*code[None,:],.25*code[:,None]*c*phase[None,:]],
                [.25*phase[:,None]*c*code[None,:],phase[:,None]*c*phase[None,:]]])
    q=(q+q.T)*.5  # covariance is exactly symmetric despite multiply-order roundoff
    b=np.vstack((h,h)); integer=np.arange(m)-2; models=[]; truth=[]
    for k in range(count):
        bearing=.3+.8*k; tilt=.12*np.sin(k)
        baseline=.35*np.array([np.cos(bearing)*np.cos(tilt),np.sin(bearing)*np.cos(tilt),np.sin(tilt)])
        y=a@integer+b@baseline
        groups=tuple(GroupDD(key,pivot,targets,y[list(rows)],a[np.ix_(rows,cols)],b[list(rows)],
                    q[np.ix_(rows,rows)],tuple(labels[i] for i in cols),rows,cols)
                    for key,pivot,targets,rows,cols in descriptions)
        models.append(MultiGnssEpoch(10+.2*k,y,a.copy(),b.copy(),q.copy(),tuple(labels),groups,
                      {'arc_label_policy':'EXPLICIT_SD_ARCS','baseline_frame':'ECEF'}))
        truth.append(baseline)
    return tuple(models),integer,np.array(truth)


@pytest.fixture
def library():
    p=Path(__file__).resolve().parents[2]/'configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json'
    if not p.exists(): pytest.skip('local pinned RTKLIB library config unavailable')
    lib=Path(json.loads(p.read_text())['aliases']['<EXT_REPRO_BUILD>'])/'lib/librtklib_legsa.so'
    if not lib.is_file(): pytest.skip('pinned RTKLIB LAMBDA bridge unavailable')
    return lib


def test_default_cap6_subset_matrices_equal_independent_index_oracle_with_full_Q():
    models,_,_=fixture_models()
    plan=selected.prepare_selected_likelihood(models,length_m=.35)
    assert plan.ready and len(plan.selection.selected_labels)==6
    assert plan.selection==preselect_partial_labels(models,PartialPolicy(max_ambiguities=6))
    assert plan.problem.ambiguity_count==6 and plan.problem.y.size==5*(9+6)
    for original,reduced,mapping in zip(models,plan.epochs,plan.supports):
        columns=[original.ambiguity_labels.index(label) for label in plan.selection.selected_labels]
        rows=tuple(range(9))+tuple(9+i for i in sorted(columns))
        assert mapping.rows_retained==rows
        assert mapping.selected_source_columns==tuple(columns)
        assert mapping.source_rows==18 and mapping.source_ambiguities==9
        assert mapping.source_code_rows==mapping.source_phase_rows==9
        assert mapping.retained_code_rows==9 and mapping.retained_phase_rows==6
        assert np.array_equal(reduced.y,original.y[list(rows)])
        assert np.array_equal(reduced.A,original.A[np.ix_(rows,columns)])
        assert np.array_equal(reduced.B,original.B[list(rows)])
        assert np.array_equal(reduced.Q,original.Q[np.ix_(rows,rows)])
        assert np.count_nonzero(reduced.Q-np.diag(np.diag(reduced.Q)))>0
        dropped=sorted(set(range(18))-set(rows))
        conditional=original.Q[np.ix_(rows,rows)]-original.Q[np.ix_(rows,dropped)]@np.linalg.solve(
            original.Q[np.ix_(dropped,dropped)],original.Q[np.ix_(dropped,rows)])
        assert np.max(abs(reduced.Q-conditional))>1e-8
        assert reduced.time_s==original.time_s
    for i,ri in enumerate(plan.problem.row_slices):
        for j,rj in enumerate(plan.problem.row_slices):
            if i!=j: assert not np.any(plan.problem.Q[ri,rj])


def test_general_mixed_row_dependency_withheld_and_column_and_row_order_preserved():
    a=np.array([[0,0,0],[.2,0,0],[0,.3,0],[.2,.3,0],[.2,0,.4],[0,0,.4]])
    q=np.diag(np.arange(1,7))+.1*np.ones((6,6))
    permutation=[5,0,3,1,4,2]
    block=EpochBlock(2,np.arange(6.)[permutation],a[permutation],np.arange(18.).reshape(6,3)[permutation],
                     q[np.ix_(permutation,permutation)],('a','b','c'),{'baseline_frame':'ECEF'})
    reduced,counts=selected.restrict_selected_observations(block,('c','a'))
    rows=(0,1,3,4)
    assert counts.rows_retained==rows and counts.rows_withheld==(2,5)
    assert counts.selected_source_columns==(2,0)
    assert reduced.ambiguity_labels==('c','a')
    assert np.array_equal(reduced.A,block.A[np.ix_(rows,[2,0])])
    assert np.array_equal(reduced.Q,block.Q[np.ix_(rows,rows)])
    assert counts.retained_code_rows==1 and counts.retained_phase_rows==3


def test_selected_columns_realign_across_epochs_and_no_input_aliasing():
    models,_,_=fixture_models()
    plan=selected.prepare_selected_likelihood(models,length_m=.35)
    target=tuple(reversed(plan.selection.selected_labels))
    permutation=np.array([8,2,0,7,5,1,4,3,6])
    original=models[0]
    permuted=EpochBlock(original.time_s,original.y.copy(),original.A[:,permutation].copy(),original.B.copy(),
                       original.Q.copy(),tuple(original.ambiguity_labels[i] for i in permutation),dict(original.metadata))
    reduced,mapping=selected.restrict_selected_observations(permuted,target)
    oracle,other=selected.restrict_selected_observations(original,target)
    assert np.array_equal(reduced.A,oracle.A) and reduced.ambiguity_labels==target
    before=reduced.y.copy(); permuted.y[:]=999
    assert np.array_equal(reduced.y,before)
    reduced.Q[0,0]+=1
    assert not np.array_equal(reduced.Q,permuted.Q[:len(reduced.Q),:len(reduced.Q)])
    with pytest.raises(TemporalModelError,match='missing/reset'):
        selected.restrict_selected_observations(original,('unknown-arc',))


def test_full_selected_set_recovers_original_likelihood_up_to_column_permutation():
    models,_,_=fixture_models()
    plan=selected.prepare_selected_likelihood(models,length_m=.35,policy=PartialPolicy(max_ambiguities=9))
    original=assemble_epochs(models,length_m=.35)
    columns=[original.ambiguity_labels.index(label) for label in plan.problem.ambiguity_labels]
    for name in ('y','B','Q','times','lengths'):
        assert np.array_equal(getattr(plan.problem,name),getattr(original,name))
    assert np.array_equal(plan.problem.A,original.A[:,columns])
    assert all(not s.rows_withheld for s in plan.supports)


def sphere_oracle(center,covariance,length):
    # Independent diagonal secular equation; fixture has no hard-pole case.
    weights,vectors=np.linalg.eigh(np.linalg.inv(covariance))
    coordinates=vectors.T@center
    rhs=weights*coordinates
    f=lambda mu:float(np.sum((rhs/(weights+mu))**2)-length**2)
    low=np.nextafter(-weights[0],np.inf)
    high=max(1.,weights[-1])
    while f(high)>0: high*=2
    assert f(low)>0
    multiplier=brentq(f,low,high,xtol=1e-10,rtol=1e-14)
    return vectors@(rhs/(weights+multiplier))


def dense_cost(epochs,integer,length):
    cost=0.
    for block in epochs:
        residual=block.y-block.A@integer
        precision=np.linalg.inv(block.Q)
        covariance=np.linalg.inv(block.B.T@precision@block.B)
        center=covariance@block.B.T@precision@residual
        baseline=sphere_oracle(center,covariance,length)
        error=residual-block.B@baseline
        cost+=float(error@precision@error)
    return cost


def test_known_integer_and_second_match_exhaustive_oracle_and_discarded_y_invariance(library):
    models,integer,truth=fixture_models(m=5,count=2)
    policy=PartialPolicy(selection_epochs=2,max_ambiguities=4)
    plan=selected.prepare_selected_likelihood(models,length_m=.35,policy=policy)
    n=np.array([integer[models[0].ambiguity_labels.index(label)] for label in plan.selection.selected_labels])
    result=selected.solve_selected_likelihood(plan,library,timeout_s=15.)
    assert result.result.certificate.global_optimum_certified
    assert np.array_equal(result.result.best.ambiguity,n)
    assert np.max(abs(result.result.best.baselines-truth))<1e-8
    brute=sorted((dense_cost(plan.epochs,n+np.array(offset),.35),tuple(n+np.array(offset)))
                  for offset in itertools.product(range(-1,2),repeat=4))
    assert tuple(result.result.best.ambiguity)==brute[0][1]
    assert tuple(result.result.second.ambiguity)==brute[1][1]
    assert result.result.best.full_residual_cost==pytest.approx(brute[0][0],abs=1e-8)
    assert result.result.second.full_residual_cost==pytest.approx(brute[1][0],abs=1e-7)
    changed=[]
    for model,mapping in zip(models,plan.supports):
        y=model.y.copy(); y[list(mapping.rows_withheld)]+=1e6
        changed.append(replace(model,y=y))
    altered=selected.prepare_selected_likelihood(changed,length_m=.35,policy=policy)
    assert altered.selection==plan.selection and altered.fingerprint==plan.fingerprint
    again=selected.solve_selected_likelihood(altered,library,timeout_s=15.)
    assert again.result.certificate.global_optimum_certified
    assert np.array_equal(again.result.best.ambiguity,result.result.best.ambiguity)
    assert np.array_equal(again.result.second.ambiguity,result.result.second.ambiguity)
    pair=selected.freeze_selected_likelihood_candidates(plan,result,source_id='synthetic')
    assert all(x.source_id.startswith(selected.LIKELIHOOD_KIND+':'+plan.fingerprint+':') for x in pair)
    assert all(x.selected_at==models[-1].time_s and x.active_labels==plan.selection.selected_labels for x in pair)
    with pytest.raises(TemporalModelError,match='not bound'):
        selected.freeze_selected_likelihood_candidates(plan,result.result,source_id='old-full-result')
    plan.problem.y[0]+=1
    with pytest.raises(TemporalModelError,match='not bound'):
        selected.freeze_selected_likelihood_candidates(plan,result,source_id='changed-problem')


def test_unavailable_selection_creates_no_zero_integer_model():
    models,_,_=fixture_models()
    bad=tuple(replace(m,B=np.column_stack((m.B[:,:2],np.zeros(len(m.B))))) for m in models)
    plan=selected.prepare_selected_likelihood(bad,length_m=.35)
    assert not plan.ready and plan.search_plan is None and not plan.epochs
    with pytest.raises(TemporalModelError,match='unavailable'):
        selected.solve_selected_likelihood(plan,'unused-library')
