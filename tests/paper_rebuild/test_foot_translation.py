"""25 local synthetic/domain tests, no real data or navigation backend."""
from dataclasses import replace
import inspect
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase.contact_rotation import FootPositionEpoch
from legsa_gins.paper_rebuild.carrier_phase.foot_translation import (
    FootTranslationError, RelativeRotationInterval, estimate_foot_interval_translation,
    interval_displacement_jacobians,
)

POINTS = np.array([[.3,.2,.45],[.3,-.2,.45],[-.3,.2,.45],[-.3,-.2,.45]])
IDS = ("FR", "FL", "RR", "RL")


def exp(vector):
    angle = np.linalg.norm(vector)
    if angle == 0:
        return np.eye(3)
    axis = vector / angle
    k = np.array([[0.,-axis[2],axis[1]],[axis[2],0.,-axis[0]],[-axis[1],axis[0],0.]])
    return np.eye(3) + np.sin(angle)*k + (1-np.cos(angle))*(k@k)


def epoch(points, t, ids=None, frame="FRD", tokens=None, stance=None, available=None):
    ids = IDS[:len(points)] if ids is None else ids
    return FootPositionEpoch(t, t if available is None else available, ids, points,
        (True,)*len(points) if stance is None else stance,
        tuple(v+":0" for v in ids) if tokens is None else tokens, frame)


def rotation(r, start=1., end=1.1, available=None):
    return RelativeRotationInterval(start,end,end if available is None else available,r,
        "synthetic_known_R",True,True,False,"LEFT_BODY0_FRD")


def setup(n=4, vector=(.2,-.1,.3), displacement=(.08,-.03,.02)):
    r = exp(np.asarray(vector))
    p0 = POINTS[:n]
    t = np.asarray(displacement)
    p1 = (p0-t)@r
    return epoch(p0,1.), epoch(p1,1.1), rotation(r), t


def covariance(n, seed=120):
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(6*n+6,6*n+6))
    scales = np.r_[np.full(6*n,.001),np.full(3,.01),np.full(3,.003)]
    return (a@a.T+np.eye(6*n+6))*np.outer(scales,scales)


def estimate(a,b,r,*,sigma=None,lever=(.03,.02,-.3),continuity=None,**kwargs):
    n=len(a.foot_ids)
    return estimate_foot_interval_translation(
        a,b,relative_rotation=r,imu_lever_body_frd_m=lever,
        joint_covariance=covariance(n) if sigma is None else sigma,
        interval_continuous_support=dict.fromkeys(a.foot_ids,True) if continuity is None else continuity,
        position_source_id="synthetic_sdk_positions",lever_source_id="explicit_synthetic_lever",
        covariance_source_id="known_synthetic_joint_working_model",**kwargs)


def finite_difference(function, size, eps=1e-7):
    return np.column_stack([(function(eps*np.eye(size)[i])-function(-eps*np.eye(size)[i]))/(2*eps)
                            for i in range(size)])


def test_rigid_interval_recovers_body_displacement_and_keeps_claim_limits():
    a,b,r,t=setup()
    out=estimate(a,b,r)
    np.testing.assert_allclose(out.body_origin_displacement_body0_frd_m,t,atol=1e-14)
    assert out.conditional_translation_rank==3 and out.residual_dof==9
    assert out.residual_cost_working_model<1e-22
    assert not out.imu_statistical_independence_proven
    assert not out.no_slip_proven and not out.navigation_admission
    assert not out.common_slip_observable
    assert out.output_measurand=="FINITE_INTERVAL_DISPLACEMENT_NOT_CURRENT_VELOCITY"


def test_translation_is_interval_displacement_not_divided_by_dt():
    a,b,r,t=setup(vector=(0,0,0))
    longer=replace(b,time_s=2.,available_time_s=2.)
    out=estimate(a,longer,rotation(np.eye(3),end=2.))
    np.testing.assert_allclose(out.body_origin_displacement_body0_frd_m,t,atol=1e-14)
    short=estimate(a,b,r)
    np.testing.assert_allclose(out.body_origin_displacement_body0_frd_m,
                               short.body_origin_displacement_body0_frd_m)
    assert out.dt_s!=short.dt_s
    assert not any("velocity" in name for name in out.__dataclass_fields__)


def test_pure_rotation_moves_nonzero_lever_imu_point():
    a,b,r,_=setup(displacement=(0,0,0))
    lever=np.array([.1,-.04,-.3])
    out=estimate(a,b,r,lever=lever)
    np.testing.assert_allclose(out.body_origin_displacement_body0_frd_m,0,atol=1e-14)
    expected=(r.matrix_body1_to_body0_frd-np.eye(3))@lever
    np.testing.assert_allclose(out.imu_point_displacement_body0_frd_m,expected,atol=1e-14)
    assert np.linalg.norm(expected)>.02


def test_single_foot_given_rotation_has_no_slip_residual_dof():
    a,b,r,t=setup(n=1)
    out=estimate(a,b,r)
    np.testing.assert_allclose(out.body_origin_displacement_body0_frd_m,t,atol=1e-14)
    assert out.residual_dof==0 and out.residual_cost_working_model<1e-23
    assert not out.no_slip_proven


def test_differential_slip_has_nonzero_multi_foot_residual_not_automatic_admission():
    a,b,r,_=setup()
    positions=b.positions_m.copy()
    positions[0]+=np.array([.03,-.02,0])@r.matrix_body1_to_body0_frd
    slipped=epoch(positions,b.time_s)
    out=estimate(a,slipped,r)
    assert np.linalg.norm(out.residuals_body0_frd_m)>.02
    assert out.residual_cost_working_model>0
    assert out.residual_dof==9 and not out.navigation_admission


def test_common_slip_is_indistinguishable_from_translation():
    a,b,r,t=setup()
    common_shift=np.array([.04,-.03,.01])
    # Fixed body displacement t, all world contacts move by common_shift.
    moved=epoch(b.positions_m+common_shift@r.matrix_body1_to_body0_frd,b.time_s)
    out=estimate(a,moved,r)
    np.testing.assert_allclose(out.body_origin_displacement_body0_frd_m,t-common_shift,atol=1e-14)
    assert out.residual_cost_working_model<1e-21
    assert not out.common_slip_observable and not out.no_slip_proven


def test_endpoint_and_left_rotation_jacobian_matches_independent_fd():
    a,b,r,_=setup(n=3)
    p0,p1=a.positions_m,b.positions_m
    matrix=r.matrix_body1_to_body0_frd
    size=24
    def measurements(delta):
        left=exp(delta[18:21])@matrix
        return ((p0+delta[:9].reshape(3,3))-
                (p1+delta[9:18].reshape(3,3))@left.T).ravel()
    jac,_=interval_displacement_jacobians(matrix,p1,[.1,-.02,.2])
    np.testing.assert_allclose(jac,finite_difference(measurements,size),atol=9e-10)


def test_rotation_lever_correction_jacobian_matches_independent_fd():
    _,b,r,_=setup(n=2)
    lever=np.array([.07,-.04,.3]); size=18
    def correction(delta):
        left=exp(delta[12:15])@r.matrix_body1_to_body0_frd
        return (left-np.eye(3))@(lever+delta[15:18])
    _,jac=interval_displacement_jacobians(r.matrix_body1_to_body0_frd,b.positions_m,lever)
    np.testing.assert_allclose(jac,finite_difference(correction,size),atol=9e-10)


def test_complete_body_imu_fixed_weight_jacobian_matches_independent_fd():
    a,b,r,_=setup(n=3)
    lever=np.array([.08,-.03,.25])
    out=estimate(a,b,r,lever=lever)
    def forward(delta):
        left=exp(delta[18:21])@r.matrix_body1_to_body0_frd
        y=((a.positions_m+delta[:9].reshape(3,3))-
           (b.positions_m+delta[9:18].reshape(3,3))@left.T).ravel()
        origin=out.gls_mean_matrix@y
        point=origin+(left-np.eye(3))@(lever+delta[21:24])
        return np.r_[origin,point]
    np.testing.assert_allclose(out.body_imu_joint_jacobian,
                               finite_difference(forward,24),atol=1e-9)


def test_dense_full_q_gls_and_joint_covariance_oracle():
    a,b,r,_=setup()
    noisy=epoch(b.positions_m+np.array([[.001,0,0],[0,.002,0],[0,0,-.001],[.001,.001,0]]),b.time_s)
    sigma=covariance(4,880)
    out=estimate(a,noisy,r,sigma=sigma)
    design=np.tile(np.eye(3),(4,1))
    q=out.per_foot_covariance_m2
    information=design.T@np.linalg.solve(q,design)
    expected=np.linalg.solve(information,design.T@np.linalg.solve(q,out.per_foot_displacements_body0_frd_m.ravel()))
    np.testing.assert_allclose(out.body_origin_displacement_body0_frd_m,expected,atol=1e-13)
    np.testing.assert_allclose(out.body_imu_joint_covariance_m2,
        out.body_imu_joint_jacobian@sigma@out.body_imu_joint_jacobian.T,atol=1e-17)
    np.testing.assert_allclose(out.body_imu_joint_covariance_m2[:3,:3],
                               np.linalg.inv(information),rtol=1e-12,atol=1e-17)


def test_zeroing_cross_terms_changes_result_and_is_not_assumed():
    a,b,r,_=setup()
    sigma=covariance(4,42)
    diagonal_blocks=np.zeros_like(sigma)
    for start,end in ((0,24),(24,27),(27,30)):
        diagonal_blocks[start:end,start:end]=sigma[start:end,start:end]
    full=estimate(a,b,r,sigma=sigma)
    independent=estimate(a,b,r,sigma=diagonal_blocks)
    assert np.linalg.norm(full.body_imu_joint_covariance_m2-independent.body_imu_joint_covariance_m2)>1e-5
    assert not full.imu_statistical_independence_proven


def test_exact_rotation_and_lever_psd_model_allowed_no_artificial_noise_floor():
    a,b,r,_=setup()
    sigma=np.zeros((30,30))
    sigma[:24,:24]=np.eye(24)*1e-6
    out=estimate(a,b,r,sigma=sigma,lever=(0,0,0))
    cov=out.body_imu_joint_covariance_m2
    np.testing.assert_allclose(cov[:3,:3],cov[:3,3:],atol=1e-20)
    np.testing.assert_allclose(cov[:3,:3],cov[3:,3:],atol=1e-20)
    assert np.linalg.matrix_rank(cov)==3


def test_flu_current_reordering_preserves_mean_and_all_cross_covariance():
    a,b,r,_=setup()
    sigma=covariance(4,150)
    original=estimate(a,b,r,sigma=sigma)
    f=np.diag([1.,-1.,-1.]); order=[2,0,3,1]
    p=np.eye(12)[np.array([[3*i,3*i+1,3*i+2] for i in order]).ravel()]
    transform=np.eye(30)
    transform[:12,:12]=np.kron(np.eye(4),f)
    transform[12:24,12:24]=p@np.kron(np.eye(4),f)
    new0=epoch(a.positions_m@f,a.time_s,frame="FLU")
    new1=epoch(b.positions_m[order]@f,b.time_s,
               ids=tuple(IDS[i] for i in order),frame="FLU")
    changed=estimate(new0,new1,r,sigma=transform@sigma@transform.T)
    np.testing.assert_allclose(changed.body_origin_displacement_body0_frd_m,
                               original.body_origin_displacement_body0_frd_m,atol=1e-13)
    np.testing.assert_allclose(changed.body_imu_joint_covariance_m2,
                               original.body_imu_joint_covariance_m2,rtol=1e-12,atol=1e-17)


def test_changed_episode_with_both_stance_true_is_unavailable():
    a,b,r,_=setup(n=1)
    b=epoch(b.positions_m,b.time_s,tokens=("FR:new",))
    out=estimate(a,b,r)
    assert out.status=="UNAVAILABLE_NO_CONTINUOUS_SUPPORT"
    assert out.body_origin_displacement_body0_frd_m is None
    assert out.body_imu_joint_covariance_m2 is None
    assert "CONTACT_EPISODE_CHANGED" in out.excluded_feet["FR"]


def test_unknown_interval_continuity_not_inferred_from_endpoints():
    a,b,r,_=setup(n=1)
    out=estimate(a,b,r,continuity={"FR":None})
    assert out.conditional_translation_rank==0
    assert out.residual_dof is None and out.residual_cost_working_model is None


def test_unavailable_feet_are_subsetted_without_dropping_joint_cross_terms():
    a,b,r,_=setup()
    sigma=covariance(4,444)
    subset=estimate(a,b,r,sigma=sigma,continuity={"FR":True,"FL":False,"RR":True,"RL":False})
    selection=[0,1,2,6,7,8,12,13,14,18,19,20,24,25,26,27,28,29]
    direct=estimate(epoch(a.positions_m[[0,2]],a.time_s,ids=("FR","RR")),
                    epoch(b.positions_m[[0,2]],b.time_s,ids=("FR","RR")),r,
                    sigma=sigma[np.ix_(selection,selection)])
    assert subset.foot_ids==("FR","RR")
    np.testing.assert_allclose(subset.body_imu_joint_covariance_m2,
                               direct.body_imu_joint_covariance_m2,atol=1e-17)
    np.testing.assert_allclose(subset.body_origin_displacement_body0_frd_m,
                               direct.body_origin_displacement_body0_frd_m,atol=1e-14)


def test_rotation_availability_sets_decision_and_future_use_is_rejected():
    a,b,r,_=setup()
    late=replace(r,available_time_s=1.2)
    out=estimate(a,b,late)
    assert out.available_time_s==1.2
    with pytest.raises(FootTranslationError,match="past-only"):
        estimate(a,b,late,decision_time_s=1.15)


def test_rotation_interval_mismatch_is_not_silently_resampled():
    a,b,r,_=setup()
    wrong=replace(r,start_time_s=.9)
    with pytest.raises(FootTranslationError,match="match exactly"):
        estimate(a,b,wrong)


def test_incomplete_rotation_or_rank_deficient_completion_is_rejected():
    _,_,r,_=setup()
    with pytest.raises(FootTranslationError,match="rank-deficient"):
        replace(r,derived_from_rank_deficient_contact=True)
    with pytest.raises(FootTranslationError,match="full relative"):
        replace(r,fully_specified_rotation_declared=False)


def test_rotation_frame_source_and_so3_contracts_are_explicit():
    _,_,r,_=setup()
    with pytest.raises(FootTranslationError,match="SO\\(3\\)"):
        replace(r,matrix_body1_to_body0_frd=np.diag([1,1,-1]))
    with pytest.raises(FootTranslationError,match="GNSS-free"):
        replace(r,gnss_free_declared=False)
    with pytest.raises(FootTranslationError,match="LEFT_BODY0_FRD"):
        replace(r,perturbation_convention="RIGHT_BODY1")
    with pytest.raises(FootTranslationError,match="source"):
        replace(r,source_id="")


def test_indefinite_asymmetric_or_wrong_size_joint_covariance_rejected():
    a,b,r,_=setup()
    bad=np.eye(30); bad[24,24]=-1.
    with pytest.raises(FootTranslationError,match="semidefinite"):
        estimate(a,b,r,sigma=bad)
    bad=np.eye(30); bad[0,1]=.1
    with pytest.raises(FootTranslationError,match="symmetric"):
        estimate(a,b,r,sigma=bad)
    with pytest.raises(FootTranslationError,match="dimensions"):
        estimate(a,b,r,sigma=np.eye(24))


def test_singular_propagated_q_is_rejected_not_floored():
    a,b,r,_=setup()
    with pytest.raises(FootTranslationError,match="positive definite"):
        estimate(a,b,r,sigma=np.zeros((30,30)))


def test_required_lever_and_source_ids_have_no_implicit_defaults():
    signature=inspect.signature(estimate_foot_interval_translation)
    for name in ("imu_lever_body_frd_m","position_source_id","lever_source_id","covariance_source_id"):
        assert signature.parameters[name].default is inspect.Parameter.empty
    a,b,r,_=setup()
    with pytest.raises(FootTranslationError,match="lever source"):
        estimate_foot_interval_translation(a,b,relative_rotation=r,imu_lever_body_frd_m=[0,0,0],
            joint_covariance=covariance(4),interval_continuous_support=dict.fromkeys(IDS,True),
            position_source_id="positions",lever_source_id="",covariance_source_id="model")


def test_rotation_snapshot_copies_input_and_reports_no_imu_independence():
    matrix=exp(np.array([.1,.2,.3]))
    recorded=rotation(matrix)
    expected=matrix.copy()
    matrix[:]=0
    np.testing.assert_array_equal(recorded.matrix_body1_to_body0_frd,expected)
    assert not recorded.matrix_body1_to_body0_frd.flags.writeable
    assert not recorded.imu_statistical_independence_proven


def test_rotation_source_declaration_does_not_certify_position_or_combined_source():
    a,b,r,t=setup()
    out=estimate(a,b,r)
    assert out.gnss_free_rotation_provenance_declared is True
    assert out.gnss_free_position_provenance_declared is None
    assert out.gnss_free_provenance_declared is None
    assert out.imu_statistical_independence_proven is False
    np.testing.assert_allclose(out.body_origin_displacement_body0_frd_m,t,atol=1e-14)
