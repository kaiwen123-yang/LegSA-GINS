"""Independent synthetic checks: SD injections, dense GLS, aliases, arc resets."""
from dataclasses import replace
import json

import numpy as np
import pytest
from scipy.special import gammaincc

from legsa_gins.paper_rebuild.carrier_phase import faults as f
from legsa_gins.paper_rebuild.carrier_phase.multignss import (
    MultiGnssEpoch, GroupDD, SignalIdentity, signal_spec)
from legsa_gins.paper_rebuild.carrier_phase.temporal import assemble_epochs, TemporalModelError
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import identity_text


def model(groups=((0,0,0),), targets=4, time=1., token="arc"):
    m = len(groups)*targets
    A = np.vstack([np.zeros((m,m)),np.diag([
        signal_spec(SignalIdentity(*[gnss,1,sig,freq])).wavelength_m
        for gnss,sig,freq in groups for _ in range(targets)])])
    # Nonparallel per-target geometry, separately constructed from fault maps.
    h = np.array([[1.,.1,.2],[.2,1.,.3],[.1,.2,1.],[.6,-.3,.7]])[:targets]
    H = np.vstack([h+np.array([.03*k,-.02*k,.01*k]) for k in range(len(groups))])
    B = np.vstack([H,H])
    labels, ids = [], []
    for gnss,sig,freq in groups:
        pivot = SignalIdentity(gnss,1,sig,freq)
        sats = tuple(SignalIdentity(gnss,j+2,sig,freq) for j in range(targets))
        ids.append((pivot,sats))
        labels.extend(json.dumps([identity_text(s),token,identity_text(pivot),token]) for s in sats)
    truth = np.arange(m,dtype=int)-3
    baseline = np.array([.17,-.21,.23])
    # Correlated raw SD covariance projected by independently written incidence.
    total_sd = len(groups)*(targets+1)
    incidence = np.zeros((m,total_sd))
    for k in range(len(groups)):
        for j in range(targets):
            incidence[k*targets+j,k*(targets+1)] = -1
            incidence[k*targets+j,k*(targets+1)+j+1] = 1
    T = np.block([[incidence,np.zeros_like(incidence)],[np.zeros_like(incidence),incidence]])
    sigma = np.r_[np.linspace(.12,.24,total_sd),np.linspace(.002,.004,total_sd)]
    sd = np.diag(sigma*sigma)
    load = np.linspace(-.4,.6,2*total_sd)*sigma
    sd += np.outer(load,load)  # Includes cross-group, cross-code/phase terms.
    Q = T @ sd @ T.T
    y = A@truth+B@baseline
    built = []
    for k,(key,(pivot,sats)) in enumerate(zip(groups,ids)):
        cc = tuple(range(k*targets,(k+1)*targets))
        rr = cc+tuple(c+m for c in cc)
        built.append(GroupDD(key,pivot,sats,y[list(rr)],A[np.ix_(rr,cc)],
                           B[list(rr)],Q[np.ix_(rr,rr)],tuple(labels[c] for c in cc),rr,cc))
    return MultiGnssEpoch(time,y,A,B,Q,tuple(labels),tuple(built),
                          {"receiver_order":"GNSS2_MINUS_GNSS1"}),truth,baseline


def inject_raw_sd(epoch, cycles):
    # This injection intentionally never calls build_phase_fault_map.
    delta = np.zeros(len(epoch.y))
    for group in epoch.groups:
        for j,target in enumerate(group.satellites):
            delta[group.row_indices[len(group.satellites)+j]] = (
                cycles.get(target,0.)-cycles.get(group.pivot,0.))*signal_spec(target).wavelength_m
    return replace(epoch,y=epoch.y+delta)


def test_pivot_fault_is_all_group_phase_rows_not_one_dd():
    epoch,n,_=model(groups=((0,0,0),(0,3,0)))
    mapping=f.build_phase_fault_map(epoch)
    group=epoch.groups[0];wave=signal_spec(group.pivot).wavelength_m
    pivot=mapping.hypotheses.index(next(h for h in mapping.hypotheses if h.signal==group.pivot))
    np.testing.assert_array_equal(mapping.matrix[:8,pivot],0)
    np.testing.assert_allclose(mapping.matrix[list(group.row_indices[4:]),pivot],-wave)
    np.testing.assert_array_equal(mapping.matrix[list(epoch.groups[1].row_indices),pivot],0)
    damaged=inject_raw_sd(epoch,{group.pivot:.25})
    np.testing.assert_allclose(damaged.y-epoch.y,.25*mapping.matrix[:,pivot],atol=1e-16)


@pytest.mark.parametrize("is_pivot",[False,True])
def test_true_scalar_bias_and_likelihood_improvement(is_pivot):
    epoch,n,b=model();group=epoch.groups[0]
    signal=group.pivot if is_pivot else group.satellites[2]
    fit=f.fixed_integer_gls(inject_raw_sd(epoch,{signal:.375}),n)
    diagnosis=f.single_fault_glrt(fit,f.build_phase_fault_map(epoch))
    score=next(s for s in diagnosis.scores if s.key=="sd:"+identity_text(signal))
    assert score.bias_cycles==pytest.approx(.375,abs=2e-12)
    assert score.residual_cost<1e-22
    assert score.improvement==pytest.approx(fit.residual_cost,rel=1e-11)
    assert diagnosis.best_hypotheses==(score.key,)
    assert score.holm_p_value>=score.nominal_p_value
    assert not diagnosis.accepted_integer_measurement


def test_full_covariance_matches_independent_dense_augmented_gls():
    epoch,n,_=model(groups=((0,0,0),(2,6,0)))
    epoch=replace(epoch,y=epoch.y+np.linspace(-.02,.035,len(epoch.y)))
    mapping=f.build_phase_fault_map(epoch)
    fit=f.fixed_integer_gls(epoch,n)
    diagnosis=f.single_fault_glrt(fit,mapping)
    W=np.linalg.inv(epoch.Q)
    r=epoch.y-epoch.A@n
    center=np.linalg.solve(epoch.B.T@W@epoch.B,epoch.B.T@W@r)
    np.testing.assert_allclose(fit.bhat,center,rtol=1e-11,atol=1e-12)
    np.testing.assert_allclose(fit.Cb,np.linalg.inv(epoch.B.T@W@epoch.B),rtol=1e-10)
    for j,score in enumerate(diagnosis.scores):
        X=np.column_stack([epoch.B,mapping.matrix[:,j]])
        estimate=np.linalg.solve(X.T@W@X,X.T@W@r)
        residual=r-X@estimate
        assert score.bias_cycles==pytest.approx(estimate[-1],rel=1e-9,abs=1e-10)
        assert score.residual_cost==pytest.approx(residual@W@residual,rel=1e-10,abs=1e-10)
    diagonal=f.fixed_integer_gls(replace(epoch,Q=np.diag(np.diag(epoch.Q))),n)
    assert not np.isclose(diagonal.residual_cost,fit.residual_cost,rtol=.01)


def test_unknown_arc_and_reordered_subset_keep_original_row_mapping():
    epoch,n,_=model()
    candidate=dict(zip(epoch.ambiguity_labels,map(int,n)))
    candidate.pop(epoch.ambiguity_labels[1])
    rows=tuple(reversed(range(len(epoch.y))))
    fit=f.fixed_integer_gls(epoch,candidate,rows=rows)
    assert fit.rows_retained==(7,6,4,3,2,1,0)
    assert fit.rows_withheld==(5,)
    assert fit.unknown_labels==(epoch.ambiguity_labels[1],)
    mapping=f.build_phase_fault_map(epoch,rows=fit.rows_retained)
    diagnosis=f.single_fault_glrt(fit,mapping)
    key="sd:"+identity_text(epoch.groups[0].satellites[1])
    assert key in diagnosis.unobservable_hypotheses
    assert mapping.row_indices==fit.rows_retained
    assert fit.residual_cost<1e-23
    with pytest.raises(TemporalModelError,match="lacks"):
        f.single_fault_glrt(fit,mapping.subset(fit.rows_retained[:-1]))


def test_receiver_signs_and_explicit_reversed_order():
    epoch,_,_=model()
    sd=f.build_phase_fault_map(epoch)
    r1=f.build_phase_fault_map(epoch,receiver="receiver1")
    r2=f.build_phase_fault_map(epoch,receiver="receiver2")
    np.testing.assert_array_equal(r2.matrix,sd.matrix)
    np.testing.assert_array_equal(r1.matrix,-sd.matrix)
    reverse=replace(epoch,metadata={"receiver_order":"GNSS1_MINUS_GNSS2"})
    np.testing.assert_array_equal(f.build_phase_fault_map(reverse,receiver="receiver1").matrix,r2.matrix)
    np.testing.assert_array_equal(f.build_phase_fault_map(reverse,receiver="receiver2").matrix,r1.matrix)


def test_multifrequency_fault_units_are_cycles_with_distinct_wavelengths():
    epoch,n,_=model(groups=((0,0,0),(0,3,0),(2,6,0)))
    mapping=f.build_phase_fault_map(epoch)
    assert len({h.wavelength_m for h in mapping.hypotheses})==3
    for group in epoch.groups:
        target=group.satellites[0]
        fit=f.fixed_integer_gls(inject_raw_sd(epoch,{target:-.2}),n)
        diagnosis=f.single_fault_glrt(fit,mapping)
        score=next(s for s in diagnosis.scores if s.key=="sd:"+identity_text(target))
        assert score.bias_cycles==pytest.approx(-.2,abs=1e-12)


def test_two_satellite_pivot_target_are_unidentifiable_sign_aliases():
    epoch,n,_=model(targets=1)
    mapping=f.build_phase_fault_map(epoch)
    damaged=inject_raw_sd(epoch,{epoch.groups[0].pivot:.25})
    diagnosis=f.single_fault_glrt(f.fixed_integer_gls(damaged,n),mapping)
    assert len(diagnosis.best_hypotheses)==2
    assert all(s.status=="ALIASED" for s in diagnosis.scores)
    assert all(len(s.equivalent_hypotheses)==2 for s in diagnosis.scores)
    assert diagnosis.scores[0].bias_cycles==pytest.approx(-diagnosis.scores[1].bias_cycles)


def test_fault_absorbed_by_rank_deficient_nuisance_is_unobservable():
    epoch,n,_=model()
    mapping=f.build_phase_fault_map(epoch)
    B=np.column_stack([mapping.matrix[:,1],np.zeros((len(epoch.y),2))])
    damaged=replace(epoch,B=B,y=epoch.A@n+B@np.array([.3,0,0]))
    fit=f.fixed_integer_gls(damaged,n)
    assert fit.baseline_rank==1
    diagnosis=f.single_fault_glrt(fit,mapping)
    assert mapping.hypotheses[1].key in diagnosis.unobservable_hypotheses
    score=diagnosis.scores[1]
    assert score.bias_cycles is None and score.incremental_df==0


def test_temporal_free_baselines_and_full_cross_epoch_q():
    first,n,_=model()
    second=replace(first,time_s=2.,y=first.y+first.B@np.array([.1,-.05,.02]))
    problem=assemble_epochs([first,second])
    Q=problem.Q.copy()
    chol=np.linalg.cholesky(first.Q)
    Q[:8,8:]=.2*chol@chol.T;Q[8:,:8]=Q[:8,8:].T
    problem=assemble_epochs([first,second],temporal_covariance=Q)
    fit=f.fixed_integer_gls(problem,n)
    assert fit.baseline_rank==6 and fit.residual_df==10
    assert fit.residual_cost<1e-23
    np.testing.assert_allclose(fit.bhat[3:]-fit.bhat[:3],[.1,-.05,.02],atol=1e-12)
    assert fit.nominal_p_value==pytest.approx(1.)
    np.testing.assert_allclose(fit.Cb,np.linalg.inv(problem.B.T@np.linalg.solve(Q,problem.B)),rtol=1e-10,atol=1e-14)


def test_persistent_stacking_shares_only_identical_sd_arcs():
    first,n,_=model()
    second=replace(first,time_s=2.)
    third,_,_=model(time=3.,token="reset")
    maps=[f.build_phase_fault_map(e) for e in (first,second,third)]
    persistent=f.stack_phase_fault_maps(maps,persistent=True)
    local=f.stack_phase_fault_maps(maps)
    assert persistent.matrix.shape==(24,10)
    assert local.matrix.shape==(24,15)
    assert persistent.original_row_count==24
    np.testing.assert_array_equal(persistent.matrix[:8,:5],persistent.matrix[8:16,:5])
    np.testing.assert_array_equal(persistent.matrix[16:,:5],0)
    np.testing.assert_array_equal(persistent.matrix[:16,5:],0)
    # Arc reset changes N labels as well; caller freezes both synthetic known arcs here.
    problem=assemble_epochs([first,second,third])
    truth=dict(zip(first.ambiguity_labels,map(int,n)))
    truth.update(zip(third.ambiguity_labels,map(int,n)))
    offset=.3*persistent.matrix[:,1]
    fit=f.fixed_integer_gls(replace(problem,y=problem.y+offset),truth)
    diagnosis=f.single_fault_glrt(fit,persistent)
    assert diagnosis.best_hypotheses==(persistent.hypotheses[1].key,)
    assert diagnosis.scores[1].bias_cycles==pytest.approx(.3,abs=1e-12)


def test_stacked_subset_offsets_use_original_not_retained_lengths():
    epoch,_,_=model()
    mapping=f.build_phase_fault_map(epoch,rows=(7,3,2))
    stacked=f.stack_phase_fault_maps([mapping,mapping],persistent=True)
    assert stacked.row_indices==(7,3,2,15,11,10)
    assert stacked.original_row_count==16


def test_persistent_sharing_requires_explicit_tokens():
    epoch,_,_=model()
    mapping=f.build_phase_fault_map(epoch)
    unknown=replace(mapping,hypotheses=tuple(replace(h,sd_arc_token=None) for h in mapping.hypotheses))
    with pytest.raises(TemporalModelError,match="explicit SD arc"):
        f.stack_phase_fault_maps([unknown,unknown],persistent=True)


def test_holm_all_estimable_hypotheses_and_global_chisquare_tail():
    epoch,n,_=model()
    epoch=replace(epoch,y=epoch.y+np.linspace(-.006,.004,8))
    fit=f.fixed_integer_gls(epoch,n)
    diagnosis=f.single_fault_glrt(fit,f.build_phase_fault_map(epoch))
    ordered=sorted(diagnosis.scores,key=lambda s:s.nominal_p_value)
    running=0.
    for j,score in enumerate(ordered):
        running=max(running,(len(ordered)-j)*score.nominal_p_value)
        assert score.holm_p_value==pytest.approx(min(1.,running))
    assert fit.nominal_p_value==pytest.approx(gammaincc(fit.residual_df/2,fit.residual_cost/2))
    assert fit.residual_df==5


@pytest.mark.parametrize("bad",[True,2.0,2.5,2**53])
def test_reject_non_exact_integer_values(bad):
    epoch,n,_=model()
    values=list(map(int,n));values[0]=bad
    with pytest.raises(TemporalModelError,match="exactly represented"):
        f.fixed_integer_gls(epoch,values)


def test_fail_closed_bad_rows_mapping_and_q():
    epoch,n,_=model()
    with pytest.raises(TemporalModelError,match="unique"):
        f.fixed_integer_gls(epoch,n,rows=(0,0))
    with pytest.raises(TemporalModelError,match="positive definite"):
        f.fixed_integer_gls(replace(epoch,Q=np.zeros_like(epoch.Q)),n)
    bad=replace(epoch.groups[0],row_indices=(0,1,2,3,4,5,6,6))
    with pytest.raises(TemporalModelError,match="mapping"):
        f.build_phase_fault_map(replace(epoch,groups=(bad,)))
    with pytest.raises(TemporalModelError,match="difference order"):
        f.build_phase_fault_map(replace(epoch,metadata={}))


def test_group_common_mode_cancels_and_no_residual_dof_is_untestable():
    epoch,n,_=model(groups=((0,0,0),(0,3,0)))
    mapping=f.build_phase_fault_map(epoch)
    for group in epoch.groups:
        indices=[j for j,h in enumerate(mapping.hypotheses) if h.group==group.key]
        np.testing.assert_allclose(mapping.matrix[:,indices].sum(axis=1),0.,atol=1e-16)
    saturated=replace(epoch,B=np.eye(len(epoch.y)))
    fit=f.fixed_integer_gls(saturated,n)
    assert fit.residual_df==0 and fit.nominal_p_value is None
    diagnosis=f.single_fault_glrt(fit,mapping)
    assert diagnosis.tested_hypotheses==0 and diagnosis.best_hypotheses==()
    assert all(s.status=="UNOBSERVABLE_AFTER_NUISANCE" for s in diagnosis.scores)


def test_pivot_change_retains_own_arc_fault_column_and_changes_row_design():
    from legsa_gins.paper_rebuild.carrier_phase.multignss import pivot_transform
    epoch,n,_=model()
    old=epoch.groups[0]
    newpivot=old.satellites[1]
    all_ids=(old.pivot,*old.satellites)
    T=pivot_transform(all_ids,old.pivot,newpivot)
    C=np.block([[T,np.zeros_like(T)],[np.zeros_like(T),T]])
    targets=tuple(sorted(i for i in all_ids if i!=newpivot))
    labels=tuple(json.dumps([identity_text(i),"arc",identity_text(newpivot),"arc"]) for i in targets)
    new=GroupDD(old.key,newpivot,targets,C@epoch.y,epoch.A.copy(),
                C@epoch.B,C@epoch.Q@C.T,labels,tuple(range(8)),tuple(range(4)))
    changed=replace(epoch,time_s=2.,y=new.y,A=new.A,B=new.B,Q=new.Q,
                    ambiguity_labels=labels,groups=(new,))
    before=f.build_phase_fault_map(epoch)
    after=f.build_phase_fault_map(changed)
    stacked=f.stack_phase_fault_maps([before,after],persistent=True)
    assert len(stacked.hypotheses)==5
    for j,h in enumerate(before.hypotheses):
        k=next(k for k,g in enumerate(after.hypotheses) if g.signal==h.signal)
        np.testing.assert_allclose(after.matrix[:,k],C@before.matrix[:,j],atol=1e-15)
    assert next(h for h in stacked.hypotheses if h.signal==old.pivot).is_pivot is None
    assert all(h.pivot is None for h in stacked.hypotheses)
