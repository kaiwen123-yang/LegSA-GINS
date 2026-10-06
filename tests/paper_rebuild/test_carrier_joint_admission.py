"""Joint gates: dense GLS oracle, conservative geometry and causal safeguards."""
from dataclasses import replace
import numpy as np
import pytest
from scipy.linalg import block_diag
from scipy.stats import chi2

from legsa_gins.paper_rebuild.carrier_phase.admission import FrozenCandidate
from legsa_gins.paper_rebuild.carrier_phase.joint_admission import (
    JointAdmissionConfig,JointCausalAdmissionSession)
from legsa_gins.paper_rebuild.carrier_phase.temporal import (
    EpochBlock,TemporalModelError,assemble_epochs)
from legsa_gins.paper_rebuild.carrier_phase.faults import fixed_integer_gls

LABELS=("a","b","c","d")
N=np.array([2,-1,4,3],dtype=int)
L=.350
W=.190293672798365


def candidate(name="best",delta=0,active=LABELS,extra=None):
    mapping=dict(zip(LABELS,map(int,N)));mapping["a"]+=delta
    if extra is not None:mapping["retired"]=extra
    return FrozenCandidate.from_mapping(name,0.,mapping,active,"synthetic-selected-candidate")


def fixtures(rho=.7,noise=None,length=L,extra_unknown=False):
    blocks=[];truth=[]
    for k in range(5):
        H=np.array([[1.,.1,.2],[.2,1.,.3],[.1,.2,1.],[.6,-.3,.7]])
        H[3]+=[.04*k,-.02*k,.03*k]
        B=np.vstack([H,H]);A=np.vstack([np.zeros((4,4)),W*np.eye(4)])
        b=length*np.array([np.cos(.2*k)*np.cos(.1),np.sin(.2*k)*np.cos(.1),np.sin(.1)])
        Q=np.diag([.01**2]*4+[.02**2]*4)
        v=np.linspace(-.002,.004,8);Q+=np.outer(v,v)
        y=A@N+B@b
        if noise is not None:y=y+np.asarray(noise)*(1+.1*k)
        labels=LABELS
        if extra_unknown:
            expanded=np.zeros((9,5));expanded[:8,:4]=A;expanded[8,4]=W;A=expanded
            B=np.vstack([B,[.1,.2,.3]]);y=np.r_[y,123.]
            q=np.zeros((9,9));q[:8,:8]=Q;q[8,8]=.002
            q[0,8]=q[8,0]=.00005;Q=q
            labels=LABELS+("unselected_arc",)
        blocks.append(EpochBlock(.2*(k+1),y,A,B,Q,labels))
        truth.append(b)
    factors=block_diag(*[np.linalg.cholesky(b.Q) for b in blocks])
    T=rho**np.abs(np.subtract.outer(np.arange(5),np.arange(5)))
    Q=factors@np.kron(T,np.eye(len(blocks[0].y)))@factors.T
    return blocks,Q,np.asarray(truth)


def session(Q,primary=None,competitor=None,independent=True,config=None):
    return JointCausalAdmissionSession(primary or candidate(),competitor or candidate("second",2),
        future_covariance=Q,covariance_source_id="explicit-synthetic-known-covariance",
        config=config or JointAdmissionConfig(selection_independent_working_model=independent))


def finish(s,blocks):
    for b in blocks:s.observe(b)
    return s.finalize()


def test_known_correlated_q_nominal_shadow_gate_and_threshold_allocation():
    blocks,Q,_=fixtures()
    d=finish(session(Q),blocks)
    assert d.status=="JOINT_SHADOW_ACCEPTED" and d.shadow_accepted
    assert d.primary.residual_df==25 and d.primary.baseline_rank==15
    assert d.primary.residual_cost<1e-23 and d.primary.length_penalty_sum<1e-22
    assert d.primary.residual_threshold==pytest.approx(chi2.isf(.005,25))
    assert len(d.primary.length_gates)==5
    assert all(x.df==3 and x.nominal_alpha==.001 for x in d.primary.length_gates)
    assert all(x.threshold==pytest.approx(chi2.isf(.001,3)) for x in d.primary.length_gates)
    assert not d.competitor.passes
    assert d.false_fix_probability is None
    assert not d.accepted_integer_measurement and not d.production_measurement
    assert not d.primary.full_joint_sphere_cost_computed
    assert not d.all_integer_alternatives_tested


def test_full_covariance_matches_independent_dense_gls_and_marginal_cb():
    noise=np.array([.004,-.002,.006,.001,-.003,.008,-.005,.002])
    blocks,Q,truth=fixtures(noise=noise)
    d=finish(session(Q),blocks)
    problem=assemble_epochs(blocks)
    y=problem.y-problem.A@N
    weight=np.linalg.inv(Q)
    covariance=np.linalg.inv(problem.B.T@weight@problem.B)
    center=covariance@problem.B.T@weight@y
    residual=y-problem.B@center
    np.testing.assert_allclose(d.primary.joint_baseline_center_m,center,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(d.primary.joint_baseline_covariance_m2,covariance,rtol=1e-10,atol=1e-13)
    assert d.primary.residual_cost==pytest.approx(residual@weight@residual,rel=1e-10)
    assert np.max(np.abs(covariance[:3,3:6]))>1e-6
    for k,g in enumerate(d.primary.length_gates):
        marginal=covariance[3*k:3*k+3,3*k:3*k+3]
        np.testing.assert_allclose(g.baseline_covariance_m2,marginal,rtol=1e-10)
        delta=center[3*k:3*k+3]-truth[k]
        assert g.penalty<=delta@np.linalg.solve(marginal,delta)+1e-10
    # This also verifies that no diagonal or block-diagonal replacement was made.
    naive=finish(session(block_diag(*[b.Q for b in blocks])),blocks)
    assert abs(naive.primary.residual_cost-d.primary.residual_cost)>1e-4


def test_block_diagonal_special_case_matches_sum_of_free_epoch_gls():
    blocks,Q,_=fixtures(rho=0,noise=np.linspace(-.005,.008,8))
    d=finish(session(Q),blocks)
    fits=[fixed_integer_gls(b,N) for b in blocks]
    assert d.primary.residual_cost==pytest.approx(sum(f.residual_cost for f in fits))
    for k,f in enumerate(fits):
        np.testing.assert_allclose(d.primary.length_gates[k].baseline_center_m,f.bhat,atol=1e-12)
        np.testing.assert_allclose(d.primary.length_gates[k].baseline_covariance_m2,f.Cb,atol=1e-13)


def test_marginal_q_does_not_restore_candidate_selection_independence():
    blocks,Q,_=fixtures(rho=.8)
    d=finish(session(Q,independent=False),blocks)
    assert d.primary.passes and not d.competitor.passes
    assert d.status=="UNRESOLVED_SELECTION_DEPENDENCE" and not d.shadow_accepted
    assert d.alpha_correct_candidate_nominal_type_i is None
    assert d.alpha_total_registered==.01
    assert JointAdmissionConfig().selection_independent_working_model is False


def test_unknown_q_is_not_estimated_or_replaced_by_epoch_independence():
    blocks,_,_=fixtures()
    d=finish(session(None),blocks)
    assert d.status=="UNRESOLVED_COVARIANCE_UNAVAILABLE"
    assert not d.full_future_covariance_provided
    assert d.primary is None and d.competitor is None
    assert d.covariance_sha256 is None
    assert d.alpha_correct_candidate_nominal_type_i is None


def test_missing_and_later_slots_never_replace_registered_horizon():
    blocks,Q,_=fixtures()
    s=session(Q)
    for k in (0,2,3,4):s.observe(blocks[k])
    d=s.finalize()
    assert d.status=="UNRESOLVED_MISSING_FUTURE_SUPPORT"
    assert d.primary is None and not d.validated_labels
    s=session(Q)
    with pytest.raises(TemporalModelError,match="outside"):s.observe(replace(blocks[4],time_s=1.2))


def test_future_order_finalization_and_duplicate_guards():
    blocks,Q,_=fixtures();s=session(Q)
    with pytest.raises(TemporalModelError,match="strictly future"):
        s.observe(replace(blocks[0],time_s=0.))
    s.observe(blocks[0])
    with pytest.raises(TemporalModelError,match="strictly future"):s.observe(blocks[0])
    s.observe(blocks[2])
    with pytest.raises(TemporalModelError,match="time ordered"):s.observe(blocks[1])
    s.finalize()
    with pytest.raises(TemporalModelError,match="already finalized"):s.finalize()
    with pytest.raises(TemporalModelError,match="already finalized"):s.observe(blocks[3])


def test_changed_active_arc_is_not_admitted_from_surviving_subset():
    blocks,Q,_=fixtures()
    blocks[2]=replace(blocks[2],ambiguity_labels=("new_arc","b","c","d"))
    d=finish(session(Q),blocks)
    assert d.status=="UNRESOLVED_ACTIVE_ARC_CHANGED"
    assert d.unvalidated_selected_labels==("a",)
    assert d.epochs[2].rows_withheld==(4,)
    assert d.primary.residual_df==24


def test_unknown_arc_common_mask_uses_full_covariance_principal_submatrix():
    blocks,Q,_=fixtures(extra_unknown=True)
    d=finish(session(Q),blocks)
    assert d.status=="JOINT_SHADOW_ACCEPTED"
    assert all(x.rows_withheld==(8,) for x in d.epochs)
    retained=tuple(k*9+j for k in range(5) for j in range(8))
    assert d.primary.retained_global_rows==retained
    problem=assemble_epochs(blocks)
    B=problem.B[list(retained)];y=(problem.y-problem.A@np.r_[N,0])[list(retained)]
    cov=Q[np.ix_(retained,retained)]
    Wt=np.linalg.solve(cov,B);Cb=np.linalg.inv(B.T@Wt)
    center=Cb@B.T@np.linalg.solve(cov,y)
    np.testing.assert_allclose(d.primary.joint_baseline_center_m,center,atol=1e-11)
    np.testing.assert_allclose(d.primary.joint_baseline_covariance_m2,Cb,atol=1e-12)


def test_covariance_and_observations_are_snapshotted_not_mutable_inputs():
    blocks,Q,_=fixtures();s=session(Q)
    for b in blocks:s.observe(b)
    Q[:]=np.eye(len(Q))*999
    for b in blocks:
        b.y[:]=999
        b.B[:]=0
    d=s.finalize()
    assert d.status=="JOINT_SHADOW_ACCEPTED"
    assert d.primary.residual_cost<1e-23


def test_q_marginal_and_dimension_mismatch_are_unresolved():
    blocks,Q,_=fixtures()
    d=finish(session(Q*2),blocks)
    assert d.status=="UNRESOLVED_INSUFFICIENT_VALIDATION"
    assert any("marginal" in r for r in d.reasons)
    d=finish(session(np.eye(len(Q)+1)),blocks)
    assert d.status=="UNRESOLVED_INSUFFICIENT_VALIDATION"
    assert any("dimensions" in r for r in d.reasons)
    with pytest.raises(TemporalModelError,match="positive definite"):session(np.zeros_like(Q))


def test_rank_deficiency_remains_unresolved():
    blocks,Q,_=fixtures()
    blocks[0]=replace(blocks[0],B=np.zeros_like(blocks[0].B))
    d=finish(session(Q),blocks)
    assert d.status=="UNRESOLVED_INSUFFICIENT_VALIDATION"
    assert d.primary is None
    assert any("rank" in r for r in d.reasons)


def test_same_active_class_and_no_future_driven_candidate_replacement():
    blocks,Q,_=fixtures()
    d=finish(session(Q,primary=candidate(extra=0),competitor=candidate("second",extra=1)),blocks)
    assert d.status=="UNRESOLVED_SAME_ACTIVE_CLASS"
    d=finish(session(Q,primary=candidate("wrong",2),competitor=candidate("truth")),blocks)
    assert d.status.startswith("REJECTED")
    assert d.competitor.passes and not d.shadow_accepted


def test_sphere_distance_bonferroni_rejection_without_product_sphere_solver():
    blocks,Q,_=fixtures(length=.7)
    d=finish(session(Q),blocks)
    assert d.primary.residual_cost<1e-22
    assert not d.primary.length_pass and d.status=="REJECTED_LENGTH"
    assert all(g.penalty>g.threshold for g in d.primary.length_gates)


def test_two_plausible_candidates_remain_unresolved():
    blocks,Q,_=fixtures()
    blocks=[replace(b,Q=10000*b.Q) for b in blocks]
    d=finish(session(10000*Q),blocks)
    assert d.primary.passes and d.competitor.passes
    assert d.status=="UNRESOLVED_COMPETITION"


@pytest.mark.parametrize("bad",[None,"",123])
def test_provenance_required(bad):
    _,Q,_=fixtures()
    with pytest.raises(TemporalModelError,match="provenance"):
        JointCausalAdmissionSession(candidate(),candidate("second",2),
            future_covariance=Q,covariance_source_id=bad)
