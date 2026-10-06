"""Independent geometry/power checks for fixed-N physical-signal sensitivity."""
from dataclasses import replace
from types import SimpleNamespace
import math
import numpy as np
import pytest
from scipy.stats import norm
from legsa_gins.paper_rebuild.carrier_phase.faults import (
    fixed_integer_gls,PhaseFaultMap,PhaseFaultHypothesis)
from legsa_gins.paper_rebuild.carrier_phase.multignss import SignalIdentity
from legsa_gins.paper_rebuild.carrier_phase.sensitivity import analyze_phase_fault_sensitivity
from legsa_gins.paper_rebuild.carrier_phase.temporal import TemporalModelError

WAVE=.190293672798365

def fixture(epochs=1,full_temporal_covariance=True):
    m=4;h=np.array([[1.,.2,.1],[.1,1.,.3],[.2,.1,1.],[.6,-.4,.5]])
    rows=2*m*epochs;A=np.zeros((rows,m));B=np.zeros((rows,3*epochs))
    F=np.zeros((rows,m+1))
    for k in range(epochs):
        r=slice(8*k,8*(k+1));A[r]=np.vstack((np.zeros((m,m)),WAVE*np.eye(m)))
        B[r,3*k:3*(k+1)]=np.vstack((h,h))
        F[8*k+4:8*k+8,:4]=WAVE*np.eye(m)
        F[8*k+4:8*k+8,4]=-WAVE
    base=np.zeros((8,8));base[:4,:4]=.2**2*(np.eye(4)+np.ones((4,4)))
    base[4:,4:]=.004**2*(np.eye(4)+np.ones((4,4)))
    T=.3**np.abs(np.arange(epochs)[:,None]-np.arange(epochs)[None,:]) if full_temporal_covariance else np.eye(epochs)
    Q=np.kron(T,base)
    loading=np.linspace(-.2,.3,rows)*np.sqrt(np.diag(Q))
    Q+=np.outer(loading,loading)  # dense time and code/phase covariance
    N=np.array([2,-1,4,0]);b=np.concatenate([np.array([.15+.02*k,-.1,.25]) for k in range(epochs)])
    model=SimpleNamespace(y=A@N+B@b,A=A,B=B,Q=Q,ambiguity_labels=tuple(f"N{i}" for i in range(4)))
    pivot=SignalIdentity(0,1,0,0);hyp=[]
    for j in range(m+1):
        is_pivot=j==m;signal=pivot if is_pivot else SignalIdentity(0,j+2,0,0)
        hyp.append(PhaseFaultHypothesis("pivot" if is_pivot else f"target{j}",signal,(0,0,0),pivot,is_pivot,
                                      "sd",WAVE,model.ambiguity_labels if is_pivot else (model.ambiguity_labels[j],),"arc"))
    return model,N,PhaseFaultMap(F,tuple(hyp),tuple(range(rows)),rows)

@pytest.mark.parametrize("epochs",[1,5])
def test_full_Q_gain_and_information_match_independent_explicit_GLS(epochs):
    model,N,mapping=fixture(epochs)
    fit=fixed_integer_gls(model,N);out=analyze_phase_fault_sensitivity(fit,mapping)
    W=np.linalg.inv(model.Q);Cb=np.linalg.inv(model.B.T@W@model.B)
    baseline=np.linalg.solve(model.B.T@W@model.B,model.B.T@W@(model.y-model.A@N))
    for j,s in enumerate(out.scores):
        f=mapping.matrix[:,j]
        gain=Cb@model.B.T@W@f
        residual=f-model.B@gain
        information=float(residual@W@residual)
        shifted=np.linalg.solve(model.B.T@W@model.B,model.B.T@W@(model.y+.31*f-model.A@N))
        np.testing.assert_allclose(s.baseline_gain_m_per_cycle,gain,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(shifted-baseline,.31*gain,rtol=1e-10,atol=1e-12)
        assert s.information_cycles_inverse2==pytest.approx(information,rel=1e-10)
        assert len(s.mdb_per_epoch_bias_norm_m)==epochs
        np.testing.assert_allclose(s.mdb_per_epoch_bias_norm_m,np.linalg.norm((gain*s.mdb_cycles).reshape(epochs,3),axis=1))
        assert s.mdb_joint_bias_norm_m==pytest.approx(np.linalg.norm(gain*s.mdb_cycles))
    assert out.nuisance_dimension==3*epochs and out.epoch_count==epochs

def test_MDB_power_matches_independent_two_sided_normal_probability():
    model,N,mapping=fixture()
    out=analyze_phase_fault_sensitivity(fixed_integer_gls(model,N),mapping)
    assert out.family_hypotheses==5 and out.per_hypothesis_alpha==pytest.approx(.002)
    z=norm.isf(.001)
    assert out.two_sided_z_threshold==pytest.approx(z)
    for score in out.scores:
        mu=score.mdb_cycles*math.sqrt(score.information_cycles_inverse2)
        power=norm.sf(z-mu)+norm.cdf(-z-mu)
        assert power==pytest.approx(.95,abs=2e-12)
        assert score.mdb_power==pytest.approx(power,abs=2e-12)
        # A strictly smaller signal must have strictly smaller power.
        smaller=norm.sf(z-.99*mu)+norm.cdf(-z-.99*mu)
        assert smaller<power

def test_pivot_is_one_physical_fault_across_all_group_DDs():
    model,N,mapping=fixture(epochs=2)
    np.testing.assert_array_equal(mapping.matrix[:,4],-mapping.matrix[:,:4].sum(axis=1))
    out=analyze_phase_fault_sensitivity(fixed_integer_gls(model,N),mapping)
    pivot=out.scores[4]
    direct=replace(mapping,matrix=mapping.matrix[:,4:5],hypotheses=(mapping.hypotheses[4],))
    one=analyze_phase_fault_sensitivity(fixed_integer_gls(model,N),direct).scores[0]
    assert pivot.information_cycles_inverse2==pytest.approx(one.information_cycles_inverse2)
    np.testing.assert_allclose(pivot.baseline_gain_m_per_cycle,one.baseline_gain_m_per_cycle)
    # Same geometry but smaller family threshold, hence lower scalar-test MDB.
    assert one.mdb_cycles<pivot.mdb_cycles

def test_sign_aliases_keep_family_count_and_equal_mdb_opposite_gain():
    model,N,mapping=fixture()
    extra=replace(mapping.hypotheses[0],key="receiver_reversed_target")
    mapping=replace(mapping,matrix=np.column_stack((mapping.matrix,-mapping.matrix[:,0])),
                    hypotheses=mapping.hypotheses+(extra,))
    out=analyze_phase_fault_sensitivity(fixed_integer_gls(model,N),mapping)
    a,b=out.scores[0],out.scores[-1]
    assert out.family_hypotheses==6
    assert set(a.observational_aliases)=={"target0","receiver_reversed_target"}
    assert a.mdb_cycles==pytest.approx(b.mdb_cycles)
    np.testing.assert_allclose(a.baseline_gain_m_per_cycle,-np.array(b.baseline_gain_m_per_cycle))
    assert a.mdb_joint_bias_norm_m==pytest.approx(b.mdb_joint_bias_norm_m)

def test_baseline_absorbed_and_zero_directions_have_no_finite_MDB():
    model,N,mapping=fixture()
    hypotheses=(replace(mapping.hypotheses[0],key="absorbed"),replace(mapping.hypotheses[1],key="zero"))
    directions=np.column_stack((model.B@np.array([.1,-.2,.3]),np.zeros(len(model.y))))
    mapping=replace(mapping,matrix=directions,hypotheses=hypotheses)
    out=analyze_phase_fault_sensitivity(fixed_integer_gls(model,N),mapping)
    assert out.estimable_hypotheses==0 and out.family_hypotheses==2
    np.testing.assert_allclose(out.scores[0].baseline_gain_m_per_cycle,[.1,-.2,.3],atol=1e-13)
    for score in out.scores:
        assert score.status=="UNDETECTABLE" and score.detectable_amplitude_unbounded
        assert score.mdb_cycles is None and score.mdb_baseline_bias_m is None
        assert score.mdb_per_epoch_bias_norm_m is None

def test_unknown_rows_and_row_reordering_use_covariance_principal_submatrix():
    model,N,mapping=fixture()
    integers=dict(zip(model.ambiguity_labels,map(int,N)));integers.pop("N1")
    order=tuple(reversed(range(len(model.y))))
    fit=fixed_integer_gls(model,integers,rows=order)
    out=analyze_phase_fault_sensitivity(fit,mapping)
    assert out.rows_retained==fit.rows_retained and 5 not in out.rows_retained
    hidden=out.scores[1]
    assert hidden.status=="UNDETECTABLE"
    # Original index mapping remains valid in nonascending row order.
    kept=list(fit.rows_retained);Q=model.Q[np.ix_(kept,kept)];B=model.B[kept];W=np.linalg.inv(Q)
    f=mapping.matrix[kept,0]
    gain=np.linalg.solve(B.T@W@B,B.T@W@f)
    np.testing.assert_allclose(out.scores[0].baseline_gain_m_per_cycle,gain,rtol=1e-10,atol=1e-12)

def test_information_is_not_an_integer_correctness_test():
    model,N,mapping=fixture()
    true=fixed_integer_gls(model,N);wrong=fixed_integer_gls(model,N+np.array([1,0,0,0]))
    assert wrong.residual_cost>true.residual_cost+1.
    a=analyze_phase_fault_sensitivity(true,mapping);b=analyze_phase_fault_sensitivity(wrong,mapping)
    assert a==b  # only geometry/Q/physical fault design enter sensitivity
    assert a.integer_correctness_established is False and a.false_fix_probability is None
    assert a.accepted_integer_measurement is False

@pytest.mark.parametrize("kind",["rank","not_3K"])
def test_unsupported_nuisance_domain_rejected(kind):
    model,N,mapping=fixture()
    if kind=="rank":model.B[:,2]=0.
    else:model.B=model.B[:,:2]
    fit=fixed_integer_gls(model,N)
    with pytest.raises(TemporalModelError,match="full-rank 3K"):
        analyze_phase_fault_sensitivity(fit,mapping)

@pytest.mark.parametrize("kwargs",[{"family_alpha":0.},{"miss_probability":0.},{"miss_probability":1.},
                                   {"observability_tolerance":0.},{"observability_tolerance":float("nan")}])
def test_invalid_probabilities_and_tolerances_rejected(kwargs):
    model,N,mapping=fixture()
    with pytest.raises(TemporalModelError):
        analyze_phase_fault_sensitivity(fixed_integer_gls(model,N),mapping,**kwargs)

def test_mismatched_row_identity_and_duplicate_keys_rejected():
    model,N,mapping=fixture();fit=fixed_integer_gls(model,N)
    with pytest.raises(TemporalModelError,match="row identities"):
        analyze_phase_fault_sensitivity(fit,replace(mapping,original_row_count=99))
    with pytest.raises(TemporalModelError,match="identities"):
        analyze_phase_fault_sensitivity(fit,replace(mapping,hypotheses=(mapping.hypotheses[0],)*5))

def test_dense_covariance_is_not_replaced_by_diagonal():
    model,N,mapping=fixture(epochs=2)
    dense=analyze_phase_fault_sensitivity(fixed_integer_gls(model,N),mapping)
    diagonal=SimpleNamespace(**{**vars(model),"Q":np.diag(np.diag(model.Q))})
    other=analyze_phase_fault_sensitivity(fixed_integer_gls(diagonal,N),mapping)
    assert not np.isclose(dense.scores[4].mdb_cycles,other.scores[4].mdb_cycles,rtol=.01)
