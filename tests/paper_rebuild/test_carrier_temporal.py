"""Temporal model/search tests with known integers and genuinely moving baselines."""
from pathlib import Path
import itertools,json,math
import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase.temporal import (
    EpochBlock,TemporalModelError,assemble_epochs,joint_float,with_scalar_prior)
from legsa_gins.paper_rebuild.carrier_phase.solver import solve_temporal,evaluate_integer
from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import constrained_baseline

@pytest.fixture
def library():
    repo=Path(__file__).resolve().parents[2]
    p=repo/"configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json"
    if not p.exists():pytest.skip("local pinned RTKLIB library config unavailable")
    aliases=json.loads(p.read_text())["aliases"];lib=Path(aliases["<EXT_REPRO_BUILD>"])/"lib/librtklib_legsa.so"
    if not lib.is_file():pytest.skip("pinned RTKLIB LAMBDA bridge unavailable")
    return lib

def fixture_problem(count=5,m=4,noise=0.,seed=91,labels_after_slip=False):
    H=np.array([[.5,-.8,.2],[-.7,-.3,.4],[.2,.6,-.8],[.8,.4,.5]])[:m]
    wavelength=.190293672798365;A=np.vstack([np.zeros((m,m)),np.eye(m)*wavelength]);B=np.vstack([H,H])
    C=np.eye(m)+np.ones((m,m));Q=np.zeros((2*m,2*m));Q[:m,:m]=.03**2*C;Q[m:,m:]=.003**2*C
    integer=np.array([2,-1,4,0])[:m];rng=np.random.default_rng(seed);blocks=[];truth=[]
    for k in range(count):
        bearing=np.deg2rad(-110+170*k/max(1,count-1));tilt=np.deg2rad(8*np.sin(k))
        b=.350*np.array([np.cos(bearing)*np.cos(tilt),np.sin(bearing)*np.cos(tilt),np.sin(tilt)])
        n=integer.copy();labels=tuple(f"G:L1:s{i}:pivot0:arc0" for i in range(m))
        if labels_after_slip and k>=count//2:
            n[0]+=1;labels=(labels[0].replace("arc0","arc1"),)+labels[1:]
        y=B@b+A@n+noise*np.linalg.cholesky(Q)@rng.normal(size=2*m)
        blocks.append(EpochBlock(.2*k,y,A,B,Q,labels));truth.append(b)
    return blocks,np.array(truth),integer

def test_dynamic_ten_epoch_baseline_is_not_forced_static(library):
    blocks,truth,n=fixture_problem(count=10)
    problem=assemble_epochs(blocks);result=solve_temporal(problem,library,timeout_s=15)
    assert result.candidate_available and np.array_equal(result.best.ambiguity,n)
    assert result.best.baselines.shape==(10,3)
    assert np.max(np.abs(result.best.baselines-truth))<1e-8
    assert np.linalg.norm(result.best.baselines[0]-result.best.baselines[-1])>.65
    assert abs(result.best.objective_identity_error)<1e-8
    assert result.best.maximum_length_error_m<1e-10

def test_single_epoch_is_exact_existing_objective(library):
    from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import solve_clambda
    blocks,truth,n=fixture_problem(count=1,noise=.7)
    b=blocks[0];legacy=solve_clambda(b.y,b.A,b.B,b.Q,length_m=.350,lambda_bridge_path=library,strict=True,timeout_seconds=15.)
    result=solve_temporal(assemble_epochs(blocks),library,timeout_s=15)
    assert result.candidate_available and legacy.global_optimum_certified
    assert np.array_equal(result.best.ambiguity,legacy.best.ambiguity)
    assert np.max(abs(result.best.baselines[0]-legacy.best.baseline))<1e-7
    assert abs(result.best.reduced_cost-legacy.best.objective)<1e-5

def test_global_search_matches_bounded_exhaustive_independent_oracle(library):
    blocks,truth,n=fixture_problem(count=2,m=3,noise=.8,seed=77)
    p=assemble_epochs(blocks);f=joint_float(p);answer=solve_temporal(p,library,timeout_s=15)
    brute=[evaluate_integer(p,f,n+np.array(offset)) for offset in itertools.product(range(-2,3),repeat=3)]
    brute.sort(key=lambda x:x.full_residual_cost)
    assert answer.candidate_available
    assert np.array_equal(answer.best.ambiguity,brute[0].ambiguity)
    assert np.array_equal(answer.second.ambiguity,brute[1].ambiguity)
    assert abs(answer.best.full_residual_cost-brute[0].full_residual_cost)<1e-8
    assert abs(answer.second.full_residual_cost-brute[1].full_residual_cost)<1e-8

def test_sphere_global_minimum_isotropic_and_anisotropic():
    from scipy.optimize import minimize
    c=np.array([.2,-.4,.1]);L=.350;Q=np.eye(3)*.04
    r=constrained_baseline(c,Q,L)
    assert np.linalg.norm(r.baseline-L*c/np.linalg.norm(c))<1e-12
    Q=np.array([[.04,.003,0],[.003,.02,.001],[0,.001,.08]]);W=np.linalg.inv(Q)
    r=constrained_baseline(c,Q,L)
    costs=[]
    for initial in np.vstack([np.eye(3),-np.eye(3)])*L:
        opt=minimize(lambda x:float((x-c)@W@(x-c)),initial,
            constraints={"type":"eq","fun":lambda x:float(x@x-L*L)},method="SLSQP",
            options={"ftol":1e-13,"maxiter":300})
        assert opt.success;costs.append(opt.fun)
    assert r.objective<=min(costs)+1e-9

def test_changed_arc_gets_new_integer_column_and_recovers_slip(library):
    blocks,truth,n=fixture_problem(count=6,labels_after_slip=True)
    p=assemble_epochs(blocks);assert p.ambiguity_count==5
    result=solve_temporal(p,library,timeout_s=15)
    assert result.candidate_available
    expected=np.r_[n,n[0]+1]
    assert np.array_equal(result.best.ambiguity,expected)
    assert np.max(np.abs(result.best.baselines-truth))<1e-8

def test_cross_epoch_covariance_float_supported_but_no_false_global_certificate(library):
    blocks,truth,n=fixture_problem(count=4,noise=.5)
    independent=assemble_epochs(blocks)
    correlation=.6**np.abs(np.arange(4)[:,None]-np.arange(4)[None,:])
    full=np.kron(correlation,blocks[0].Q)
    correlated=assemble_epochs(blocks,temporal_covariance=full)
    f=joint_float(correlated);iid=joint_float(independent)
    assert np.isfinite(f.covariance).all()
    assert np.min(np.diag(f.covariance_aa)/np.diag(iid.covariance_aa))>1.5
    with pytest.raises(TemporalModelError,match="cross-epoch covariance"):
        solve_temporal(correlated,library)

def test_rp_fault_and_phase_bias_keep_full_objective_identity(library):
    blocks,truth,n=fixture_problem(count=5,noise=.5)
    # These are mechanism identity tests, not claims that biased observations recover truth.
    augmented=[with_scalar_prior(b,[0,0,1],.15,.03,name="known_fault") for b in blocks]
    p=assemble_epochs(augmented);answer=solve_temporal(p,library,timeout_s=15)
    assert answer.candidate_available
    assert abs(answer.best.objective_identity_error)<1e-5
    assert np.max(abs(np.linalg.norm(answer.best.baselines,axis=1)-.350))<1e-8
    changed=list(blocks);b=changed[2];y=b.y.copy();y[len(n)]+=.25*b.A[len(n),0]
    changed[2]=EpochBlock(b.time_s,y,b.A,b.B,b.Q,b.ambiguity_labels)
    phase=solve_temporal(assemble_epochs(changed),library,timeout_s=15)
    assert phase.candidate_available and abs(phase.best.objective_identity_error)<1e-5

def test_missing_rank_or_time_is_explicit():
    blocks,truth,n=fixture_problem(count=2)
    with pytest.raises(TemporalModelError,match="time"):
        assemble_epochs([blocks[0],blocks[0]])
    b=blocks[0];broken=EpochBlock(b.time_s,b.y,b.A,np.zeros_like(b.B),b.Q,b.ambiguity_labels)
    with pytest.raises(TemporalModelError,match="rank"):
        joint_float(assemble_epochs([broken]))
    bad=EpochBlock(b.time_s,b.y,b.A,b.B,b.Q,(b.ambiguity_labels[0],)*4)
    with pytest.raises(TemporalModelError,match="unique"):
        assemble_epochs([bad])

def test_expired_budget_never_certifies(library):
    blocks,truth,n=fixture_problem(count=4,noise=.7)
    answer=solve_temporal(assemble_epochs(blocks),library,timeout_s=1e-10)
    assert not answer.candidate_available
    assert not answer.certificate.global_optimum_certified
    assert "TIMEOUT" in answer.certificate.termination_reason

@pytest.mark.parametrize("value",[2**63,-2**63,2**53,2**53+1,10**400,float("inf"),1.5])
def test_large_or_nonintegral_candidate_is_explicitly_rejected(value):
    blocks,_,_=fixture_problem(count=1)
    p=assemble_epochs(blocks);f=joint_float(p)
    with pytest.raises(TemporalModelError):
        evaluate_integer(p,f,[value,0,0,0])

def test_selected_integer_classes_keep_historical_nuisance_and_match_enumeration(library):
    blocks,truth,n=fixture_problem(count=2,m=3,noise=.3,seed=951)
    b0,b1=blocks
    blocks=[b0,EpochBlock(b1.time_s,b1.y,b1.A,b1.B,b1.Q,("new_arc",)+b1.ambiguity_labels[1:])]
    p=assemble_epochs(blocks);f=joint_float(p)
    active=blocks[-1].ambiguity_labels
    result=solve_temporal(p,library,distinct_ambiguity_labels=active,timeout_s=15)
    assert result.candidate_available
    indices=[p.ambiguity_labels.index(x) for x in active]
    expected=np.r_[n,n[0]]
    classes={}
    for offset in itertools.product(range(-2,3),repeat=4):
        candidate=evaluate_integer(p,f,expected+np.array(offset))
        key=tuple(candidate.ambiguity[indices])
        if key not in classes or candidate.full_residual_cost<classes[key].full_residual_cost:classes[key]=candidate
    brute=sorted(classes.values(),key=lambda x:x.full_residual_cost)
    assert tuple(result.best.ambiguity[indices])!=tuple(result.second.ambiguity[indices])
    assert np.array_equal(result.best.ambiguity,brute[0].ambiguity)
    assert np.array_equal(result.second.ambiguity,brute[1].ambiguity)
    assert abs(result.second.full_residual_cost-brute[1].full_residual_cost)<1e-7
    assert result.best.ambiguity.shape==(4,)
    assert result.certificate.distinct_ambiguity_labels==active
    assert result.certificate.certificate_scope=="two_best_selected_integer_classes"

@pytest.mark.parametrize("labels",[(),("absent",),("G:L1:s0:pivot0:arc0",)*2])
def test_invalid_selected_integer_classes_rejected(library,labels):
    blocks,_,_=fixture_problem(count=1)
    with pytest.raises(TemporalModelError,match="distinct ambiguity labels"):
        solve_temporal(assemble_epochs(blocks),library,distinct_ambiguity_labels=labels)
