"""28 bounded synthetic cases; physical injections happen only in test oracles.

No real data/reference/native or integer solver. Detector input contains no
fault labels/times/truth. Finite latent enumeration is not a real risk estimate.
"""
from dataclasses import replace
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.arc_relations import SdArcNode, DdArcRelation
from legsa_gins.paper_rebuild.carrier_phase.arc_phase_difference import (
    PhaseEpoch, PhaseArcContinuity, PhaseAttitudeState, build_phase_contrast_geometry,
)
from legsa_gins.paper_rebuild.carrier_phase.arc_phase_admission import (
    AdmissionSpecification, ConditionalErrorBounds, PhaseAdmissionLedger,
    PhaseAdmissionError, assess_phase_contrast, innovation_bound, consistency_statistic,
)

BASELINE=np.array([.03,-.347,.02])
WAVE=299792458./1575.42e6
BODY="SYNTHETIC_BODY"


def skew(v):
    x,y,z=v
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])


def rot(v):
    v=np.asarray(v,float);a=np.linalg.norm(v)
    if a==0:return np.eye(3)
    k=skew(v/a)
    return np.eye(3)+np.sin(a)*k+(1-np.cos(a))*k@k


def nodes(n):
    return tuple(SdArcNode(f"0:{k+1}:0:0","arc-A") for k in range(n))


def epoch(t,ns,los,R,*,pivot=0,sd_error=None,baseline=BASELINE):
    ns=tuple(ns);n=len(ns)
    dd=np.array([np.eye(n)[k]-np.eye(n)[pivot] for k in range(n) if k!=pivot])
    edges=tuple(DdArcRelation(ns[k],ns[pivot]) for k in range(n) if k!=pivot)
    # Independent SD oracle, not production physical_integer_design/F.
    integer=np.arange(n)*7-19
    sd=-np.asarray(los)@(R@baseline)+WAVE*integer
    if sd_error is not None:sd=sd+np.asarray(sd_error)
    q=dd@np.diag(np.linspace(1.,2.,n)*1e-8)@dd.T
    return PhaseEpoch(t,t+.03,f"epoch-{t}",f"SD-oracle-{t}","pair-A","GPS_LOCAL",
        "RX2_RX1_TARGET_PIVOT_METRES",f"LOS-{t}",f"SD-noise-{t}",edges,
        dd@sd,-dd@np.asarray(los),q)


def geometry(e0,e1,keep=None):
    if keep is None:keep=set(e0.nodes)&set(e1.nodes)
    c=PhaseArcContinuity(e0.time_s,e1.time_s,
        None if e1.available_time_s is None else e1.available_time_s,
        e0.receiver_pair_id,"whole-interval-synthetic",tuple(keep))
    return build_phase_contrast_geometry(e0,e1,c)


def setup_case(*,n=9,t=100.,errors0=None,errors1=None,pivot0=0,pivot1=0,
               stationary=False,baseline=BASELINE):
    ns=nodes(n)
    rng=np.random.default_rng(27007+n)
    l0=rng.normal(size=(n,3));l0/=np.linalg.norm(l0,axis=1)[:,None]
    l1=l0.copy() if stationary else l0+.02*rng.normal(size=(n,3))
    l1/=np.linalg.norm(l1,axis=1)[:,None]
    R0=rot([.1,-.2,.3]);R1=R0 if stationary else rot([-.17,.14,.51])
    e0=epoch(t,ns,l0,R0,pivot=pivot0,sd_error=errors0,baseline=baseline)
    e1=epoch(t+.8,ns,l1,R1,pivot=pivot1,sd_error=errors1,baseline=baseline)
    g=geometry(e0,e1)
    s0=PhaseAttitudeState(t,t+.03,R0,BODY,"nominal-prior-0")
    s1=PhaseAttitudeState(t+.8,t+.83,R1,BODY,"nominal-prior-1")
    spec=AdmissionSpecification(baseline,BODY,"registered-baseline",.01,.01,0.,
        "exact-linear-test-remainder","test-error-domain",True,"LOCAL_SYNTHETIC",
        f"frozen-I-{t}",t+.9,t+.89)
    m=g.epoch0_covariance_contribution_m2+g.epoch1_covariance_contribution_m2
    bound=ConditionalErrorBounds(np.eye(6)*1e-5,np.zeros((6,6)),m,
        "FULL_DECLARED_CROSS",np.zeros((6,len(g.relations))),"state-joint",
        "explicit-zero-mean-synthetic","SD-joint-error","explicit-independent-latents",
        spec.conditioning_information_set_id,spec.frozen_at_s,t+.88,True,"LOCAL_SYNTHETIC")
    return g,s0,s1,spec,bound


def assess(case,*,ledger=None,name="a",decision=None):
    g,s0,s1,spec,bound=case
    if ledger is None:ledger=PhaseAdmissionLedger("test-ledger")
    if decision is None:decision=g.epoch1.time_s+.2
    return assess_phase_contrast(g,s0,s1,spec,bound,ledger=ledger,
                                assessment_id=name,decision_time_s=decision)


def with_bound(case,bound):
    return (*case[:4],bound)


def j_oracle(case):
    g,s0,s1,spec,_=case
    return np.hstack([g.G0@skew(s0.matrix_body_to_ecef@spec.baseline_body_m),
                      -g.G1@skew(s1.matrix_body_to_ecef@spec.baseline_body_m)])


def cross_case(sign):
    c=setup_case();m=len(c[0].relations)
    rng=np.random.default_rng(33021)
    a=rng.normal(size=(6,11))*1e-3
    b=sign*rng.normal(size=(m,11))*1e-4
    bounds=replace(c[-1],state_covariance_rad2=a@a.T,
        phase_second_moment_bound_m2=b@b.T,
        cross_second_moment_rad_m=a@b.T,cross_source_id="shared-latent-generator")
    return with_bound(c,bounds),a,b


def alias_case():
    # Physical unit LOS, with a redundant satellite sharing the pivot direction.
    ns=nodes(4);los=np.array([[1.,0,0],[0,1.,0],[0,0,1.],[1.,0,0]])
    baseline=np.array([1.,0,0]);identity=np.eye(3)
    e0=epoch(100.,ns,los,identity,baseline=baseline)
    e1=epoch(100.8,ns,los,identity,sd_error=[0.,WAVE,0.,0.],baseline=baseline)
    g=geometry(e0,e1)
    c=setup_case(n=4,baseline=baseline)
    spec=c[3]
    b=replace(c[-1],state_covariance_rad2=np.eye(6)*.1,
        phase_second_moment_bound_m2=g.epoch0_covariance_contribution_m2+g.epoch1_covariance_contribution_m2)
    return (g,replace(c[1],matrix_body_to_ecef=identity),
            replace(c[2],matrix_body_to_ecef=identity),spec,b)


def event(ledger,g,node,*,event_id="event",lo=None,hi=None,notice=102.,retire=None):
    if lo is None:lo=g.epoch0.time_s+.4
    if hi is None:hi=lo
    return ledger.invalidate(event_id=event_id,receiver_pair_id=g.epoch0.receiver_pair_id,
        node=node,interval_start_s=lo,interval_end_s=hi,notice_time_s=notice,
        source_id="separate-qualified-source-event",retire_from_s=retire)


def test_01_clean_moving_geometry_independent_oracle(record_property):
    c=setup_case();d=assess(c);g,s0,s1,spec,b=c
    assert d.status=="CONDITIONALLY_USABLE"
    np.testing.assert_allclose(d.residual_m,0.,atol=2e-14)
    np.testing.assert_allclose(d.prediction_jacobian,j_oracle(c),atol=1e-15)
    assert d.prior.dimension==len(g.relations)
    assert d.projected.dimension==len(g.relations)-d.nuisance_rank
    assert not d.navigation_admitted and d.direction_point_ecef is None
    record_property("clean_max_residual_m",float(np.max(abs(d.residual_m))))


def test_02_finite_latent_second_moment_and_markov_bound(record_property):
    # 2k-point distribution has exact second moment I; deliberately no MC.
    k=3;support=np.vstack([np.eye(k),-np.eye(k)])*np.sqrt(k)
    np.testing.assert_allclose(support.T@support/len(support),np.eye(k),atol=1e-15)
    costs=[consistency_statistic(x,np.eye(k),epsilon_m=0.,alpha=.2)[0] for x in support]
    assert np.mean([c.rejects for c in costs])<=.2
    assert np.mean([c.statistic for c in costs])==pytest.approx(k)
    record_property("exact_support_points",len(support))
    hand,_=consistency_statistic(np.array([5.]),np.eye(1),epsilon_m=2.,alpha=.2)
    covered,_=consistency_statistic(np.array([1.]),np.eye(1),epsilon_m=2.,alpha=.2)
    assert hand.statistic==pytest.approx(9.) and covered.statistic==0.
    eta=np.array([2.,0.,0.])
    for w in support:
        gate,_=consistency_statistic(w+eta,np.eye(k),epsilon_m=2.,alpha=.2)
        assert gate.statistic<=float(w@w)+1e-14


def test_03_positive_cross_matches_latent_oracle():
    c,a,b=cross_case(1);j=j_oracle(c)
    np.testing.assert_allclose(innovation_bound(j,c[-1]),(j@a+b)@(j@a+b).T,
                               rtol=1e-12,atol=1e-20)


def test_04_negative_cross_is_not_erased():
    c,a,b=cross_case(-1);j=j_oracle(c)
    actual=innovation_bound(j,c[-1])
    np.testing.assert_allclose(actual,(j@a+b)@(j@a+b).T,rtol=1e-12,atol=1e-20)
    wrong=j@(a@a.T)@j.T+b@b.T
    assert np.linalg.norm(actual-wrong)>1e-8


def test_05_complete_same_source_cancellation_is_not_independent_information():
    c=setup_case();j=j_oracle(c);p=np.eye(6)*1e-4
    bound=replace(c[-1],state_covariance_rad2=p,
        phase_second_moment_bound_m2=j@p@j.T,cross_second_moment_rad_m=-p@j.T,
        cross_source_id="exact-deterministic-reuse")
    d=assess(with_bound(c,bound))
    assert d.status=="UNRESOLVED"
    assert not d.between_factor_independence_established


def test_06_unknown_cross_bound_contains_both_extremes():
    c=setup_case();j=j_oracle(c);p=np.eye(6)*.01;m=j@p@j.T
    unknown=replace(c[-1],state_covariance_rad2=p,phase_second_moment_bound_m2=m,
        cross_mode="UNKNOWN_CROSS_BOUND",cross_second_moment_rad_m=None,
        cross_source_id="unknown-explicitly")
    upper=innovation_bound(j,unknown)
    for sign in (-1,1):
        actual=(1+sign)**2*m
        assert np.linalg.eigvalsh(upper-actual).min()>-1e-15
    assert not assess(with_bound(c,unknown)).joint_covariance_known


def test_07_indefinite_declared_joint_is_contract_error_not_slip_detection():
    c=setup_case();m=len(c[0].relations)
    with pytest.raises(ValueError,match="positive semidefinite"):
        replace(c[-1],cross_second_moment_rad_m=np.ones((6,m))*1.)


def test_08_unqualified_bias_or_source_is_unknown_without_consumption():
    c=setup_case();ledger=PhaseAdmissionLedger("unknown-source")
    d=assess(with_bound(c,replace(c[-1],qualified=False)),ledger=ledger)
    assert d.status=="UNKNOWN" and d.prior is None and d.residual_m is None
    assert ledger.consumed_endpoint_count==0


def test_09_nonzero_mean_outer_bound_is_retained():
    c=setup_case();mu=np.array([.03,-.01,.02,.01,-.04,.02])
    bound=replace(c[-1],state_mean_outer_bound_rad2=np.outer(mu,mu),
                  mean_bound_source_id="nonzero-mean-explicit")
    j=j_oracle(c)
    expected=j@(bound.state_covariance_rad2+np.outer(mu,mu))@j.T+bound.phase_second_moment_bound_m2
    np.testing.assert_allclose(innovation_bound(j,bound),expected,rtol=1e-13,atol=1e-18)


def test_10_unknown_or_future_availability_never_becomes_source_time():
    c=setup_case();g=c[0]
    unknown=geometry(replace(g.epoch0,available_time_s=None),g.epoch1)
    for case,decision in [((unknown,*c[1:]),101.),(c,100.91)]:
        ledger=PhaseAdmissionLedger("time")
        if case is c:
            case=(*c[:3],replace(c[3],available_time_s=100.95,frozen_at_s=100.96),
                  replace(c[-1],frozen_at_s=100.96))
            decision=100.96
            case=(replace(case[0],declared_available_time_s=101.2),*case[1:])
        d=assess(case,ledger=ledger,decision=decision)
        assert d.status=="UNKNOWN" and d.actual_available_time_s is None
        assert ledger.consumed_endpoint_count==0
    # Nominal/geometry may be available at decision but too late for frozen I.
    late_state=(c[0],c[1],replace(c[2],available_time_s=100.95),c[3],c[-1])
    late_geometry=(replace(c[0],declared_available_time_s=100.95),*c[1:])
    for case,reason in [(late_state,"FROZEN_STATE_NOT_AVAILABLE"),
                        (late_geometry,"FROZEN_GEOMETRY_SUPPORT_NOT_AVAILABLE")]:
        ledger=PhaseAdmissionLedger("late-conditioning-input")
        d=assess(case,ledger=ledger)
        assert d.status=="UNKNOWN" and reason in d.reasons
        assert d.residual_m is None and ledger.consumed_endpoint_count==0


def test_11_zero_nuisance_redundancy_is_unresolved():
    d=assess(setup_case(n=3))
    assert d.status=="UNRESOLVED"
    assert d.nuisance_residual_dimension==0 and d.projected is None


def test_12_singular_innovation_and_unqualified_local_remainder_are_not_loaded():
    c=setup_case();m=len(c[0].relations)
    zero=replace(c[-1],state_covariance_rad2=np.zeros((6,6)),
                 phase_second_moment_bound_m2=np.zeros((m,m)))
    d=assess(with_bound(c,zero))
    assert d.status=="UNRESOLVED"
    unknown=assess((*c[:3],replace(c[3],remainder_domain_qualified=False),c[-1]))
    assert unknown.status=="UNKNOWN" and unknown.prior is None


def test_13_small_variance_mode_cannot_be_deleted_to_pass():
    gate,why=consistency_statistic(np.array([0.,1.]),np.diag([1.,1e-10]),
                                  epsilon_m=0.,alpha=.01)
    assert why is None and gate.rejects
    gate,why=consistency_statistic(np.array([0.,1.]),np.diag([1.,1e-20]),
                                  epsilon_m=0.,alpha=.01)
    assert gate is None and why=="UNRELIABLE_POSITIVE_DEFINITE_SUPPORT"
    # Finite input whose HPHT overflows must fail closed, not normalize to zero.
    c=setup_case()
    huge=replace(c[-1],state_covariance_rad2=np.eye(6)*1e308)
    g=replace(c[0],G0=c[0].G0*1e100,G1=c[0].G1*1e100)
    d=assess((g,*c[1:4],huge))
    assert d.status=="UNRESOLVED" and not d.conditionally_usable


def test_14_detectable_target_cycle_step_is_injected_in_sd(record_property):
    errors=np.zeros(9);errors[4]=WAVE
    c=setup_case(errors1=errors);d=assess(c)
    assert d.status=="REJECTED" and d.projected.rejects
    target=next(p for p in d.fault_projections if p.node==nodes(9)[4] and p.endpoint==1)
    assert target.relative_projected_norm>.01
    record_property("target_projected_statistic",d.projected.statistic)


def test_15_pivot_cycle_step_retains_shared_dd_pattern():
    errors=np.zeros(9);errors[0]=WAVE
    d=assess(setup_case(errors1=errors))
    pivot=next(p for p in d.fault_projections if p.node==nodes(9)[0] and p.endpoint==1)
    np.testing.assert_allclose(pivot.template_m_per_cycle,-np.ones(8)*WAVE)
    assert d.status=="REJECTED" and d.projected.rejects


def test_16_fractional_sd_phase_fault_does_not_require_integer_search():
    errors=np.zeros(9);errors[6]=.25*WAVE
    d=assess(setup_case(errors1=errors))
    assert d.status=="REJECTED" and d.projected.rejects
    assert d.fault_false_acceptance_probability is None


def test_17_exact_physical_phase_pose_alias_is_not_projectedly_detectable(record_property):
    c=alias_case();d=assess(c)
    # An alternative unit baseline has exactly the same phase as this SD step.
    a=(-(1-WAVE)+np.sqrt((1-WAVE)**2-3*WAVE**2))/3
    alternative=np.array([1+a,a-WAVE,a])
    assert np.linalg.norm(alternative)==pytest.approx(1.,abs=1e-14)
    np.testing.assert_allclose(c[0].G1@(alternative-c[3].baseline_body_m),
                               [WAVE,0.,0.],atol=1e-14)
    t=next(p for p in d.fault_projections if p.node==nodes(4)[1] and p.endpoint==1)
    assert t.locally_absorbable_to_numerical_tolerance
    assert not d.projected.rejects
    record_property("alias_projected_template_norm",float(np.linalg.norm(t.projected_template_m_per_cycle)))


def test_18_fault_can_pass_both_gates_under_broad_prior():
    c=alias_case();broad=assess(c)
    tight=assess(with_bound(c,replace(c[-1],state_covariance_rad2=np.eye(6)*1e-10)))
    assert broad.status=="CONDITIONALLY_USABLE"
    assert tight.status=="REJECTED" and tight.prior.rejects
    assert not broad.phase_fault_proven and broad.fault_false_acceptance_probability is None


def test_19_wrong_prior_rejects_clean_phase_without_claiming_fault():
    c=setup_case()
    wrong=replace(c[2],matrix_body_to_ecef=np.eye(3),source_id="wrong-nominal-prior")
    d=assess((c[0],c[1],wrong,c[3],c[-1]))
    assert d.status=="REJECTED" and not d.phase_fault_proven
    assert "PRIOR_ASSISTED_MODEL_INCONSISTENT" in d.reasons


def test_20_static_geometry_and_baseline_axis_gauges_survive():
    c=setup_case(stationary=True);d=assess(c);j=d.prediction_jacobian
    b0=c[1].matrix_body_to_ecef@BASELINE;b1=c[2].matrix_body_to_ecef@BASELINE
    np.testing.assert_allclose(j@np.r_[b0,np.zeros(3)],0.,atol=1e-15)
    np.testing.assert_allclose(j@np.r_[np.zeros(3),b1],0.,atol=1e-15)
    np.testing.assert_allclose(j@np.vstack([np.eye(3),np.eye(3)]),0.,atol=1e-15)
    assert d.nuisance_rank==2 and d.direction_point_ecef is None


def test_21_coordinate_and_unit_transform_invariance_with_zero_remainder():
    c,a,b=cross_case(1);d=assess(c);z=rot([.2,-.4,.1])
    g,s0,s1,spec,bound=c
    transformed=geometry(replace(g.epoch0,geometry_ecef=g.epoch0.geometry_ecef@z.T),
                         replace(g.epoch1,geometry_ecef=g.epoch1.geometry_ecef@z.T))
    t=np.zeros((6,6));t[:3,:3]=z;t[3:,3:]=z
    bnew=replace(bound,state_covariance_rad2=t@bound.state_covariance_rad2@t.T,
                 cross_second_moment_rad_m=t@bound.cross_second_moment_rad_m)
    other=assess((transformed,replace(s0,matrix_body_to_ecef=z@s0.matrix_body_to_ecef),
                  replace(s1,matrix_body_to_ecef=z@s1.matrix_body_to_ecef),spec,bnew))
    assert d.prior.statistic==pytest.approx(other.prior.statistic,abs=1e-18)
    # Pure numerical unit transport of the gate: metre to centimetre, epsilon=0.
    residual=np.arange(1.,5.);s=np.diag([2.,3.,4.,5.])
    one,_=consistency_statistic(residual,s,epsilon_m=0.,alpha=.05)
    two,_=consistency_statistic(100*residual,1e4*s,epsilon_m=0.,alpha=.05)
    assert one.statistic==pytest.approx(two.statistic)


def test_22_pivot_reparameterization_preserves_zero_remainder_assessment():
    errors=np.zeros(9);errors[2]=WAVE/5
    first=assess(setup_case(errors1=errors))
    changed=assess(setup_case(errors1=errors,pivot0=3,pivot1=5))
    assert first.status==changed.status
    assert first.prior.statistic==pytest.approx(changed.prior.statistic,rel=1e-9)
    assert first.projected.statistic==pytest.approx(changed.projected.statistic,rel=1e-9)


def test_23_partial_full_loss_and_new_tokens_do_not_inherit_old_integers():
    c=setup_case();g=c[0];keep=g.physical_nodes[2:]
    partial=geometry(g.epoch0,g.epoch1,keep)
    b=replace(c[-1],phase_second_moment_bound_m2=
        partial.epoch0_covariance_contribution_m2+partial.epoch1_covariance_contribution_m2,
        cross_second_moment_rad_m=np.zeros((6,len(partial.relations))))
    d=assess((partial,*c[1:4],b))
    assert d.status=="CONDITIONALLY_USABLE" and len(partial.relations)<len(g.relations)
    empty=geometry(g.epoch0,g.epoch1,())
    zero=replace(c[-1],phase_second_moment_bound_m2=np.zeros((0,0)),
                 cross_second_moment_rad_m=np.zeros((6,0)))
    assert assess((empty,*c[1:4],zero)).status=="UNRESOLVED"
    new_node=replace(g.epoch1.relations[0].target,arc="new-token")
    edges=tuple(DdArcRelation(new_node if e.target==g.epoch1.relations[0].target else e.target,e.pivot)
                for e in g.epoch1.relations)
    changed=geometry(g.epoch0,replace(g.epoch1,relations=edges))
    assert new_node not in {e.target for e in changed.relations}


def test_24_canonical_endpoint_consumption_survives_rename_and_rejection():
    errors=np.zeros(9);errors[4]=WAVE
    c=setup_case(errors1=errors);ledger=PhaseAdmissionLedger("consume")
    first=assess(c,ledger=ledger)
    assert first.status=="REJECTED" and ledger.consumed_endpoint_count==2
    g=c[0]
    renamed=geometry(replace(g.epoch0,epoch_id="renamed-0",source_id="new-label-0"),
                     replace(g.epoch1,epoch_id="renamed-1",source_id="new-label-1"))
    again=assess((renamed,*c[1:]),ledger=ledger,name="b")
    assert again.reasons==("ENDPOINT_ALREADY_CONSUMED",)
    pivot=setup_case(errors1=errors,pivot0=3,pivot1=5)
    assert assess(pivot,ledger=ledger,name="c").reasons==("ENDPOINT_ALREADY_CONSUMED",)
    assert ledger.consumed_endpoint_count==2


def test_25_late_interval_invalidation_revokes_without_refund_or_filter_rollback():
    c=setup_case();ledger=PhaseAdmissionLedger("revoke")
    assert assess(c,ledger=ledger).conditionally_usable
    notice=event(ledger,c[0],c[0].physical_nodes[2])
    assert notice.revoked_assessment_ids==("a",) and ledger.state("a")=="REVOKED"
    assert not notice.external_filter_rollback_confirmed
    assert ledger.consumed_endpoint_count==2
    assert assess(c,ledger=ledger).reasons==("PREVIOUSLY_REVOKED",)


def test_26_later_retirement_preserves_history_and_bans_future_old_token():
    c=setup_case();ledger=PhaseAdmissionLedger("retire")
    assess(c,ledger=ledger)
    notice=event(ledger,c[0],c[0].physical_nodes[2],lo=101.5,notice=102.,retire=101.5)
    assert not notice.revoked_assessment_ids and ledger.state("a")=="ACTIVE"
    future=setup_case(t=103.)
    rejected=assess(future,ledger=ledger,name="b")
    assert rejected.reasons==("RETIRED_PHYSICAL_TOKEN",)
    # A later evidence interval cannot hide an earlier declared retirement.
    retrospective=PhaseAdmissionLedger("retrospective-retirement")
    assess(c,ledger=retrospective)
    backdated=event(retrospective,c[0],c[0].physical_nodes[2],
                   lo=102.,notice=103.,retire=100.4)
    assert backdated.revoked_assessment_ids==("a",)
    assert retrospective.state("a")=="REVOKED"
    assert retrospective.consumed_endpoint_count==2


def test_27_new_token_new_epochs_and_partial_survivors_require_new_assessment():
    c=setup_case();ledger=PhaseAdmissionLedger("recover");assess(c,ledger=ledger)
    old=c[0].physical_nodes[2]
    event(ledger,c[0],old,lo=100.4,notice=102.,retire=100.4)
    future=setup_case(t=103.);g=future[0]
    # Conservative partial survivor path can exclude a retired source completely.
    survivor=geometry(g.epoch0,g.epoch1,set(g.physical_nodes)-{old})
    bound=replace(future[-1],phase_second_moment_bound_m2=
        survivor.epoch0_covariance_contribution_m2+survivor.epoch1_covariance_contribution_m2,
        cross_second_moment_rad_m=np.zeros((6,len(survivor.relations))))
    assert assess((survivor,*future[1:4],bound),ledger=ledger,name="survivor").conditionally_usable
    fresh=setup_case(t=105.)
    def relabel(epoch):
        replacement=replace(old,arc="new-qualified-arc")
        edges=tuple(DdArcRelation(replacement if e.target==old else e.target,
                                 replacement if e.pivot==old else e.pivot) for e in epoch.relations)
        return replace(epoch,relations=edges)
    revived=geometry(relabel(fresh[0].epoch0),relabel(fresh[0].epoch1))
    assert assess((revived,*fresh[1:]),ledger=ledger,name="new-evidence").conditionally_usable
    assert ledger.state("a")=="REVOKED" and ledger.consumed_endpoint_count==6


def test_28_out_of_order_actions_and_duplicate_event_receipts():
    c=setup_case();ledger=PhaseAdmissionLedger("order");first=assess(c,ledger=ledger)
    assert assess(c,ledger=ledger) is first
    node=c[0].physical_nodes[1]
    notice=event(ledger,c[0],node,event_id="same")
    assert event(ledger,c[0],node,event_id="same") is notice
    with pytest.raises(PhaseAdmissionError,match="out-of-order"):
        event(ledger,c[0],node,event_id="older",notice=101.5)
    future=setup_case(t=101.)
    # Decision at 102 is earlier than the last explicit evidence at 104.
    event(ledger,c[0],node,event_id="later",lo=103.,notice=104.)
    assert assess(future,ledger=ledger,name="late").reasons==("OUT_OF_ORDER_DECISION",)
