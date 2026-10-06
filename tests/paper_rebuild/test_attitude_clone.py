"""14 bounded Gaussian/geometry checks; no real source or navigation backend."""
from dataclasses import replace
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from legsa_gins.paper_rebuild.carrier_phase.attitude_clone import (
    AttitudeCloneError, ErrorGaussian, NoiseCorrelation, ZERO_CROSS, SUPPLIED_CROSS,
    augment_attitude_clone, propagate_current, update_measurement,
    reset_after_full_feedback, marginalize_clone,
)


def base():
    rng=np.random.default_rng(610601)
    factor=.025*rng.normal(size=(21,21))+.18*np.eye(21)
    mean=np.linspace(-.015,.015,21)
    state=ErrorGaussian(mean,factor@factor.T,1.,"synthetic-latent-prior")
    j=np.zeros((3,21)); j[:,6:9]=np.eye(3)
    return state,j,factor


def process():
    phi=np.eye(21); phi[:3,3:6]=np.eye(3)*.2; phi[6:9,9:12]=-np.eye(3)*.2
    qfactor=np.diag(np.linspace(.002,.008,21))
    return phi,qfactor


def propagate(state,**kwargs):
    phi,lq=process()
    values=dict(new_time_s=1.2,process_noise_independent_of_prior=True,
                process_source_id="synthetic-white-driving-noise",
                qualification_note="independent latent draw by construction in this unit model")
    values.update(kwargs)
    return propagate_current(state,phi,lq@lq.T,**values)


def zero():
    return NoiseCorrelation(ZERO_CROSS,"synthetic-measurement-noise",
                            "zero state-noise cross only in this declared working model")


def update(state,z,h,r,*,correlation=None,identity="obs1",**kwargs):
    values=dict(correlation=zero() if correlation is None else correlation,
                measurement_id=identity,measurement_time_s=state.current_time_s,
                available_time_s=state.current_time_s)
    values.update(kwargs)
    return update_measurement(state,z,h,r,**values)


def latent_batch_qr(state_map, mean, observation_map, residual, independent_noise):
    # Independent latent standard-normal posterior as augmented least squares.
    # No covariance-Kalman recursion, no calls into implementation.
    n=state_map.shape[1]
    chol=np.linalg.cholesky(independent_noise)
    a=np.vstack((np.eye(n),np.linalg.solve(chol,observation_map)))
    b=np.r_[np.zeros(n),np.linalg.solve(chol,residual)]
    orth,upper=np.linalg.qr(a,mode="reduced")
    posterior_mean=np.linalg.solve(upper,orth.T@b)
    inverse_upper=np.linalg.solve(upper,np.eye(n))
    return mean+state_map@posterior_mean,state_map@inverse_upper@inverse_upper.T@state_map.T


def evolved():
    state,j,l0=base()
    clone=augment_attitude_clone(state,j,clone_id="pose0")
    out=propagate(clone)
    phi,lq=process()
    latent=np.block([[phi@l0,lq],[j@l0,np.zeros((3,21))]])
    return out,latent


def test_deterministic_clone_is_singular_correlated_latent_copy():
    state,j,l0=base()
    j[:,6:9]=Rotation.from_rotvec([.2,-.3,.1]).as_matrix()
    j[:,:3]=np.diag([1e-7,2e-7,0.])
    out=augment_attitude_clone(state,j,clone_id="pose0")
    latent=np.vstack((l0,j@l0))
    np.testing.assert_allclose(out.mean[21:],j@state.mean,atol=1e-16)
    np.testing.assert_allclose(out.covariance,latent@latent.T,atol=3e-17)
    cancellation=np.column_stack((-j,np.eye(3)))
    np.testing.assert_allclose(cancellation@out.covariance@cancellation.T,0,atol=3e-17)
    assert np.linalg.matrix_rank(out.covariance)==21 and out.dimension==24
    assert out.clone_time_s==state.current_time_s


def test_prediction_matches_explicit_independent_noise_latent_trajectory():
    out,latent=evolved()
    np.testing.assert_allclose(out.covariance,latent@latent.T,atol=3e-17)
    state,j,_=base(); phi,_=process()
    np.testing.assert_allclose(out.mean,np.r_[phi@state.mean,j@state.mean],atol=1e-16)
    assert out.clone_time_s==1. and out.current_time_s==1.2
    assert "PROCESS_ZERO_PRIOR_CROSS" in out.working_assumptions[-1]


def test_current_then_relative_foot_update_matches_one_independent_batch():
    state,t=evolved()
    h1=np.zeros((3,21)); h1[:,:3]=np.eye(3)
    h1[:,6:9]=np.array([[0.,-.3,.2],[.3,0.,-.1],[-.2,.1,0.]])
    # Physical foot direction: one relative attitude pair contributes rank two.
    direction=np.array([.6,-.2,.1])
    a=np.column_stack([np.cross(direction,np.eye(3)[i]) for i in range(3)])
    h2=np.zeros((3,24)); h2[:,6:9]=-a; h2[:,21:]=a
    z1=np.array([.1,-.03,.08]); z2=np.array([.01,.04,-.02])
    r1=np.diag([.008,.012,.006]); r2=np.eye(3)*.002
    after1,rec1=update(state,z1,h1,r1)
    assert rec1.padded_current_only
    assert np.linalg.norm(after1.mean[21:]-state.mean[21:])>1e-4
    assert np.linalg.norm(after1.covariance[21:,21:]-state.covariance[21:,21:])>1e-5
    after2,_=update(after1,z2,h2,r2,identity="foot")
    h1full=np.column_stack((h1,np.zeros((3,3))))
    h=np.vstack((h1full,h2)); r=np.block([[r1,np.zeros((3,3))],[np.zeros((3,3)),r2]])
    expected_mean,expected_cov=latent_batch_qr(t,state.mean,h@t,np.r_[z1,z2]-h@state.mean,r)
    np.testing.assert_allclose(after2.mean,expected_mean,atol=2e-15)
    np.testing.assert_allclose(after2.covariance,expected_cov,atol=3e-16)


def test_supplied_state_measurement_cross_covariance_matches_latent_oracle():
    state,t=evolved()
    rng=np.random.default_rng(601)
    h=rng.normal(size=(4,24))*.3
    d=rng.normal(size=(4,t.shape[1]))*.012
    independent=np.diag([.008,.012,.006,.009])
    c=t@d.T; r=d@d.T+independent
    z=np.array([.05,-.03,.04,.02])
    correlation=NoiseCorrelation(SUPPLIED_CROSS,"shared-latent-source","known D in synthetic generator",c)
    out,rec=update(state,z,h,r,correlation=correlation)
    expected_mean,expected_cov=latent_batch_qr(t,state.mean,h@t+d,z-h@state.mean,independent)
    np.testing.assert_allclose(out.mean,expected_mean,atol=2e-15)
    np.testing.assert_allclose(out.covariance,expected_cov,atol=3e-16)
    assert rec.joint_working_noise_psd_checked and not rec.physical_calibration_proven


def test_omitting_known_cross_noise_is_a_real_counterexample_not_R_inflation():
    state,t=evolved(); h=np.zeros((2,24)); h[:,:2]=np.eye(2)
    d=.7*(h@t); r=d@d.T+np.eye(2)*.003; c=t@d.T
    z=np.array([.3,-.1])
    correct,_=update(state,z,h,r,correlation=NoiseCorrelation(SUPPLIED_CROSS,"same-source","synthetic known correlation",c))
    wrong,_=update(state,z,h,r)
    assert np.linalg.norm(correct.mean-wrong.mean)>.01
    assert np.linalg.norm(correct.covariance-wrong.covariance)>.005
    assert not wrong.physical_calibration_proven and ZERO_CROSS in wrong.working_assumptions[-1]


def test_gauge_and_missing_clone_cross_covariance_counterexample():
    state,j,_=base()
    clone=augment_attitude_clone(state,j,clone_id="pose0")
    u=np.array([.4,-.1,.2])
    a=np.column_stack([np.cross(u,np.eye(3)[i]) for i in range(3)])
    h=np.zeros((3,24)); h[:,6:9]=-a; h[:,21:]=a
    gauge=np.zeros((24,3)); gauge[6:9]=np.eye(3); gauge[21:]=np.eye(3)
    np.testing.assert_allclose(h@gauge,0,atol=0)
    # At the cloning instant both poses are the same random variable:
    # the relative observation must not reduce absolute attitude uncertainty.
    out,rec=update(clone,[.01,.02,.03],h,np.eye(3)*.001)
    np.testing.assert_allclose(rec.gain,0,atol=2e-14)
    np.testing.assert_allclose(out.covariance,clone.covariance,atol=2e-16)
    wrong_cov=clone.covariance.copy(); wrong_cov[:21,21:]=0; wrong_cov[21:,:21]=0
    wrong=replace(clone,covariance=wrong_cov)
    wrongly_updated,_=update(wrong,[.01,.02,.03],h,np.eye(3)*.001)
    assert np.trace(wrongly_updated.covariance[6:9,6:9])<.8*np.trace(clone.covariance[6:9,6:9])


def test_reset_all_cross_covariances_match_independent_retraction_fd():
    state,_=evolved()
    mean=state.mean.copy(); mean[6:9]=[.25,-.17,.35]; mean[21:]=[-.2,.1,.3]
    state=replace(state,mean=mean)
    gp=np.diag([1.00003,.99997,1.])
    out,rec=reset_after_full_feedback(state,feedback_applied_error=mean,
        current_position_reset_jacobian=gp,position_reset_source_id="synthetic-DRnew-DRiold")
    def actual_new_error(eps):
        original=mean+eps
        after=original-mean
        after[:3]=gp@(original[:3]-mean[:3])
        for start in (6,21):
            after[start:start+3]=(Rotation.from_rotvec(original[start:start+3])*
                                  Rotation.from_rotvec(-mean[start:start+3])).as_rotvec()
        return after
    eye=np.eye(24); step=1e-7
    derivative=np.column_stack([(actual_new_error(step*d)-actual_new_error(-step*d))/(2*step) for d in eye])
    np.testing.assert_allclose(rec.coordinate_jacobian,derivative,atol=1e-9)
    expected=derivative@state.covariance@derivative.T
    np.testing.assert_allclose(out.covariance,expected,atol=7e-11)
    assert np.linalg.norm(out.covariance[:21,21:]-state.covariance[:21,21:])>1e-3
    assert np.array_equal(out.mean,np.zeros(24))
    assert not rec.nominal_state_modified_by_this_module and not rec.exact_nonlinear_posterior_claim


def test_retirement_takes_marginal_not_clone_conditioned_covariance():
    state,_=evolved()
    current=marginalize_clone(state)
    np.testing.assert_array_equal(current.mean,state.mean[:21])
    np.testing.assert_array_equal(current.covariance,state.covariance[:21,:21])
    conditional=state.covariance[:21,:21]-state.covariance[:21,21:]@np.linalg.solve(
        state.covariance[21:,21:],state.covariance[21:,:21])
    assert np.linalg.norm(current.covariance-conditional)>.02
    assert current.clone_id is None and current.dimension==21
    with pytest.raises(AttitudeCloneError,match="resurrected"):
        augment_attitude_clone(current,base()[1],clone_id="pose0")
    new=augment_attitude_clone(current,base()[1],clone_id="pose1")
    assert new.clone_time_s==current.current_time_s


def test_explicit_process_independence_time_and_dimensions():
    clone=augment_attitude_clone(base()[0],base()[1],clone_id="pose0")
    for value in (False,None,1):
        with pytest.raises(AttitudeCloneError,match="process noise"):propagate(clone,process_noise_independent_of_prior=value)
    for time in (1.,.9,np.nan):
        with pytest.raises(AttitudeCloneError,match="time"):propagate(clone,new_time_s=time)
    with pytest.raises(AttitudeCloneError):
        propagate_current(clone,np.eye(24),np.eye(21),new_time_s=1.2,
                          process_noise_independent_of_prior=True,process_source_id="q",qualification_note="model")


def test_supplied_C_must_be_full_and_jointly_psd_zero_mode_cannot_ignore_it():
    state,_=evolved(); h=np.eye(21)[:2]; r=np.eye(2)*.001
    with pytest.raises(AttitudeCloneError,match="complete"):
        update(state,[0.,0.],h,r,correlation=NoiseCorrelation(SUPPLIED_CROSS,"bad","model",np.zeros((21,2))))
    with pytest.raises(AttitudeCloneError,match="joint state-noise"):
        update(state,[0.,0.],h,r,correlation=NoiseCorrelation(SUPPLIED_CROSS,"bad","model",np.ones((24,2))*10))
    with pytest.raises(AttitudeCloneError,match="ignore"):
        NoiseCorrelation(ZERO_CROSS,"bad","model",np.zeros((24,2)))
    with pytest.raises(AttitudeCloneError):NoiseCorrelation(SUPPLIED_CROSS,"bad","model")
    with pytest.raises(AttitudeCloneError):NoiseCorrelation("AUTO","bad","model")


def test_psd_singular_inputs_supported_but_invalid_covariances_rejected():
    zero_state=ErrorGaussian(np.zeros(21),np.zeros((21,21)),1.,"deterministic-test")
    clone=augment_attitude_clone(zero_state,base()[1],clone_id="zero")
    out,_=update(clone,[1.],np.ones((1,21)),np.ones((1,1)))
    assert np.count_nonzero(out.covariance)==0 and np.count_nonzero(out.mean)==0
    with pytest.raises(AttitudeCloneError,match="positive definite"):
        update(clone,[1.],np.ones((1,21)),np.zeros((1,1)))
    for bad in (-np.eye(21),np.eye(21)+np.eye(21,k=1),np.full((21,21),np.nan)):
        with pytest.raises(AttitudeCloneError):ErrorGaussian(np.zeros(21),bad,1.,"bad")


def test_measurement_causality_duplicate_and_lifecycle_fail_closed():
    state,_=evolved(); h=np.eye(21)[:1]
    for time,available in ((1.,1.),(1.2,1.3),(1.2,1.1),(np.nan,1.2)):
        with pytest.raises(AttitudeCloneError,match="time"):
            update(state,[0.],h,np.eye(1),measurement_time_s=time,available_time_s=available)
    once,_=update(state,[0.],h,np.eye(1))
    with pytest.raises(AttitudeCloneError,match="consumed"):update(once,[0.],h,np.eye(1))
    with pytest.raises(AttitudeCloneError,match="one active"):
        augment_attitude_clone(state,base()[1],clone_id="second")
    with pytest.raises(AttitudeCloneError):marginalize_clone(base()[0])
    with pytest.raises(AttitudeCloneError):
        update(state,[0.],np.ones((1,23)),np.eye(1))


def test_reset_rejects_clipping_and_bad_coordinate_map():
    state,_=evolved()
    altered=state.mean.copy(); altered[6]*=.5
    with pytest.raises(AttitudeCloneError,match="clipping"):
        reset_after_full_feedback(state,feedback_applied_error=altered,
            current_position_reset_jacobian=np.eye(3),position_reset_source_id="test")
    with pytest.raises(AttitudeCloneError,match="invertible"):
        reset_after_full_feedback(state,feedback_applied_error=state.mean,
            current_position_reset_jacobian=np.zeros((3,3)),position_reset_source_id="test")
    with pytest.raises(AttitudeCloneError):
        reset_after_full_feedback(state,feedback_applied_error=state.mean,
            current_position_reset_jacobian=np.eye(3),position_reset_source_id="")


def test_current_only_21_model_and_immutable_provenance_remain_conditional():
    state,_,l=base()
    h=np.eye(21)[:3]; z=np.array([.1,.2,-.05]); r=np.eye(3)*.03
    out,rec=update(state,z,h,r)
    expected_mean,expected_cov=latent_batch_qr(l,state.mean,h@l,z-h@state.mean,r)
    np.testing.assert_allclose(out.mean,expected_mean,atol=5e-16)
    np.testing.assert_allclose(out.covariance,expected_cov,atol=3e-16)
    assert out.dimension==21 and not rec.padded_current_only
    assert not out.physical_calibration_proven and not out.navigation_admission
    assert not zero().physical_independence_proven
    for array in (state.mean,state.covariance,rec.gain,rec.innovation_covariance):
        with pytest.raises(ValueError):array.flat[0]=12.
