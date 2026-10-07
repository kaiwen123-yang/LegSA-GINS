import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/paper_rebuild/carrier_phase'))
from foot_unknown_cross_certificate import witness_check


def check(P,H,R,w):
    return witness_check(P,H,R,w,centered_model=True,conditioning_id='synthetic:frozen-before-residual')


def test_scalar_zero_cross_helps_but_allowed_cross_prevents_guarantee():
    p=np.array([[1.]]);h=np.array([[1.]]);r=np.array([[4.]])
    result=check(p,h,r,[1.]);assert result['witness_supported']
    k=1/5;assert 1-1/5<1
    assert np.allclose(p+k*k*(r-h@p@h.T),[[1.12]])


def test_dense_latent_joint_and_fixed_gain_weighted_loss():
    p=np.array([[2.,.3],[.3,1.]])
    h=np.array([[1.,.2],[-.3,.5]])
    v=np.array([[.8,.1],[.1,.4]]);r=h@p@h.T+v;c=-p@h.T
    a=np.block([[np.eye(2),np.zeros((2,2))],[-h,np.eye(2)]])
    latent=np.block([[p,np.zeros((2,2))],[np.zeros((2,2)),v]])
    joint=np.block([[p,c],[c.T,r]])
    assert np.allclose(a@latent@a.T,joint)
    k=np.array([[.4,-.2],[.1,.3]]);f=np.eye(2)-k@h
    post=f@p@f.T+k@r@k.T-f@c@k.T-k@c.T@f.T
    assert np.allclose(post,p+k@v@k.T)
    assert np.dot([1.,3.],np.diag(post-p))>0
    assert check(p,h,r,[1.,3.])['witness_supported']


def test_singular_clone_prior_requires_no_inverse():
    result=check([[1,1],[1,1]],[[1,-1]],[[2]],[1,0])
    assert result['witness_supported'] and result['T']==1


def test_exact_zero_V_does_not_claim_unique_skip():
    result=check([[1]],[[1]],[[1]],[1])
    assert result['status']=='WITNESS_EXACT_ZERO_REMAINDER' and not result['skip_uniqueness_established']


def test_indefinite_V_does_not_prove_gain():
    result=check([[4]],[[1]],[[1]],[1])
    assert result['status']=='CONDITION_NOT_SATISFIED'
    assert result['minimax_trace_working_class'] is None and result['no_guarantee_of_gain_if_condition_fails']


def test_unit_congruence_preserves_condition_and_objective():
    p=np.array([[2.,.3],[.3,1.]])
    h=np.array([[1.,.2],[-.3,.5]]);v=np.array([[.8,.1],[.1,.4]])
    r=h@p@h.T+v;w=np.array([1.,3.]);a=np.diag([1e-8,1e6]);b=np.diag([1e3,1e-4])
    base=check(p,h,r,w)
    changed=check(a@p@a.T,b@h@np.linalg.inv(a),b@r@b.T,w/np.diag(a)**2)
    assert base['witness_supported']==changed['witness_supported']
    assert np.isclose(base['T'],changed['T'])
    assert np.isclose(base['V_min_eigenvalue_normalized'],changed['V_min_eigenvalue_normalized'])


def test_nonfinite_nonsymmetric_and_negative_prior_rejected():
    with pytest.raises(ValueError):check([[float('nan')]],[[1]],[[2]],[1])
    with pytest.raises(ValueError):check([[1,.1],[.2,1]],[[1,0]],[[2]],[1,1])
    with pytest.raises(ValueError):check([[1,2],[2,1]],[[1,0]],[[2]],[1,1])


def test_close_psd_boundary_is_unresolved_without_loading():
    result=check(np.eye(2),np.eye(2),np.diag([1.+1e-14,2.]),[1.,1.])
    assert result['status']=='UNRESOLVED_PSD_BOUNDARY' and not result['witness_supported']


def test_zero_H_tiny_variance_large_weight_keeps_mass():
    result=check(np.diag([1.,1e-16]),np.zeros((1,2)),[[1.]],[1.,1e16])
    assert result['T']==2. and result['minimax_trace_working_class']==2.


def test_centering_information_identity_and_weights_required():
    with pytest.raises(ValueError):witness_check([[1]],[[1]],[[2]],[1],centered_model=False,conditioning_id='x')
    with pytest.raises(ValueError):witness_check([[1]],[[1]],[[2]],[1],centered_model=True,conditioning_id='')
    with pytest.raises(ValueError):check([[1]],[[1]],[[2]],[-1])
