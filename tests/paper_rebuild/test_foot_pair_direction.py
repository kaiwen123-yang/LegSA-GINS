"""16 bounded synthetic checks: physical world points and independent SO(3) FD."""
from dataclasses import replace
import math
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from legsa_gins.paper_rebuild.carrier_phase.contact_rotation import FootPositionEpoch
from legsa_gins.paper_rebuild.carrier_phase.foot_pair_direction import (
    BodyAttitudeLinearization, FootPairDirectionError, evaluate_foot_pair_direction,
    direction_jacobian_current_ned, clone_attitude_augmentation_jacobian,
    left_feedback_reset_jacobian,
)

IDS = ("FL", "RR")


def exp(v):
    return Rotation.from_rotvec(v).as_matrix()


def epoch(p, t, *, ids=IDS, frame="FRD", tokens=None, stance=(True, True), available=None):
    return FootPositionEpoch(t, t if available is None else available, ids, np.asarray(p),
        stance, tuple(name+":episode1" for name in ids) if tokens is None else tokens, frame)


def attitude(c, t, available=None):
    return BodyAttitudeLinearization(t, t if available is None else available, c, "filter-state")


def setup():
    # Start from fixed physical world contacts, translated/rotated body origins,
    # and a nonidentity static mount: no production residual generates the data.
    feet = np.array([[.4, .22, .03], [-.27, -.19, .06]]) + [30., -20., 2.]
    origin0 = np.array([30., -20., 2.6])
    origin1 = origin0 + [.13, -.07, .035]
    c0, c1 = exp([.25, -.13, .44]), exp([-.12, .21, .81])
    mount = exp([.02, -.03, .01])
    p0 = (feet-origin0) @ c0 @ mount
    p1 = (feet-origin1) @ c1 @ mount
    return epoch(p0, 1.), epoch(p1, 1.2), attitude(c0, 1.), attitude(c1, 1.2), mount, feet, origin0, origin1


def sigma():
    a = np.random.default_rng(60708).normal(size=(12, 12))
    return (a@a.T+np.eye(12))*1e-6


def evaluate(a=None, b=None, c0=None, c1=None, *, covariance=None, **kwargs):
    defaults = setup()
    a, b, c0, c1 = [default if given is None else given
                   for default, given in zip(defaults[:4], (a, b, c0, c1))]
    values = dict(foot_pair=IDS, attitude0=c0, attitude1=c1,
        four_point_covariance=sigma() if covariance is None else covariance,
        foot_frd_to_attitude_body=defaults[4], interval_continuous_support=dict.fromkeys(IDS, True),
        endpoint_ids=("raw:001", "raw:002"), consumed_endpoint_ids=frozenset(),
        position_source_id="sdk-body-report", position_gnss_input_used=None,
        covariance_source_id="synthetic-full-Sigma", frame_transform_source_id="known-test-mount")
    values.update(kwargs)
    return evaluate_foot_pair_direction(a, b, **values)


def fd(function, dimension, eps=1e-7):
    return np.column_stack([(function(eps*np.eye(dimension)[i]) -
                             function(-eps*np.eye(dimension)[i]))/(2*eps)
                            for i in range(dimension)])


def earth(blh):
    # Independent basis from north=east x down, plus analytic metric radii.
    lat, lon, height = blh
    east = np.array([-np.sin(lon), np.cos(lon), 0.])
    down = -np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])
    north = np.cross(east, down)
    e = np.column_stack((north, east, down))
    eccentricity_squared = 6.6943799901413156e-3
    w = 1.-eccentricity_squared*np.sin(lat)**2
    rn = 6378137./np.sqrt(w)
    rm = 6378137.*(1.-eccentricity_squared)/w**1.5
    dri = np.diag([1./(rm+height), 1./((rn+height)*np.cos(lat)), -1.])
    k = np.column_stack((-east/(rm+height), np.array([0.,0.,1.])/((rn+height)*np.cos(lat)), np.zeros(3)))
    return e, k, dri


def test_world_fixed_contacts_dynamic_pose_nonzero_lever_oracle():
    a,b,c0,c1,mount,feet,o0,o1 = setup()
    lever = np.array([.13, -.08, .04])
    for endpoint, orientation, origin in ((a,c0,o0), (b,c1,o1)):
        imu_position = origin + orientation.matrix_body_to_ecef @ lever
        world = imu_position + (endpoint.positions_m @ mount.T-lever) @ orientation.matrix_body_to_ecef.T
        np.testing.assert_allclose(world, feet, atol=1e-14)
    out = evaluate()
    np.testing.assert_allclose(out.residual_body0_m, 0, atol=1e-14)
    assert out.physical_relative_direction_rank == out.joint_linearization_rank == 2
    assert out.position_gnss_input_used is None
    assert not out.imu_statistical_independence_proven
    assert not out.absolute_heading_observed and not out.navigation_admission and not out.instantaneous_velocity


def test_endpoint_common_translation_and_rigid_lever_cancel_exactly():
    a,b,c0,c1,*_ = setup()
    old = evaluate()
    # Any separate common body translation at either endpoint cancels in d.
    changed = evaluate(replace(a, positions_m=a.positions_m+[.7,-.8,.4]),
                       replace(b, positions_m=b.positions_m+[-.3,.2,1.1]), c0,c1)
    np.testing.assert_allclose(changed.residual_body0_m, old.residual_body0_m, atol=3e-16)
    np.testing.assert_allclose(changed.residual_covariance_m2, old.residual_covariance_m2, atol=1e-19)
    # These indistinguishable common offsets include common slip, not a proof of no slip.
    assert not changed.no_slip_proven


def test_world_angular_jacobian_fd_at_nonzero_orientation_residual():
    a,b,c0,c1,mount,*_ = setup()
    c1 = attitude(exp([.3, -.2, .1]) @ c1.matrix_body_to_ecef, b.time_s)
    out = evaluate(a,b,c0,c1)
    assert np.linalg.norm(out.residual_body0_m) > .05
    d0, d1 = mount@(a.positions_m[0]-a.positions_m[1]), mount@(b.positions_m[0]-b.positions_m[1])
    def residual(delta):
        cc1 = exp(delta[:3])@c1.matrix_body_to_ecef
        cc0 = exp(delta[3:])@c0.matrix_body_to_ecef
        return d0-cc0.T@cc1@d1
    np.testing.assert_allclose(out.jacobian_world_current_clone, -fd(residual,6), atol=2e-9)


def test_ned_position_attitude_and_clone_H_match_native_retraction_fd():
    a,b,c0,c1,mount,*_ = setup()
    blh = np.array([.6, 1.1, 73.])
    e,k,dri = earth(blh)
    cbn = e.T @ (exp([.2,.1,-.15])@c1.matrix_body_to_ecef)
    current = attitude(e@cbn, b.time_s)
    out = evaluate(a,b,c0,current)
    h = direction_jacobian_current_ned(out, ecef_from_current_ned=e, ned_frame_connection_per_m=k)
    d0, d1 = mount@(a.positions_m[0]-a.positions_m[1]), mount@(b.positions_m[0]-b.positions_m[1])
    def res_position(delta):
        return d0-c0.matrix_body_to_ecef.T @ earth(blh-dri@delta)[0]@cbn@d1
    def res_phi(delta):
        return d0-c0.matrix_body_to_ecef.T@e@exp(delta)@cbn@d1
    def res_clone(delta):
        return d0-(exp(delta)@c0.matrix_body_to_ecef).T@e@cbn@d1
    np.testing.assert_allclose(h[:,:3], -fd(res_position,3,eps=1.), atol=1e-15)
    np.testing.assert_allclose(h[:,6:9], -fd(res_phi,3), atol=2e-9)
    np.testing.assert_allclose(h[:,21:], -fd(res_clone,3), atol=2e-9)
    assert np.count_nonzero(h[:,np.r_[3:6,9:21]]) == 0


def test_clone_ecef_augmentation_matches_independent_rotation_log_fd():
    blh = np.array([.8, -.3, 125.])
    e,k,dri = earth(blh)
    cbn = exp([.4,-.2,.3])
    old = e@cbn
    j = clone_attitude_augmentation_jacobian(ecef_from_ned=e, ned_frame_connection_per_m=k)
    def pos(delta):
        updated = earth(blh-dri@delta)[0]@cbn
        return Rotation.from_matrix(updated@old.T).as_rotvec()
    def phi(delta):
        updated = e@exp(delta)@cbn
        return Rotation.from_matrix(updated@old.T).as_rotvec()
    # The rotation-matrix/log oracle has O(eps_machine) roundoff in zero
    # entries; do not require a tighter-than-machine absolute tolerance.
    np.testing.assert_allclose(j[:,:3], fd(pos,3,eps=1.), atol=8*np.finfo(float).eps)
    np.testing.assert_allclose(j[:,6:9], fd(phi,3), atol=1e-9)


def test_four_point_dense_covariance_preserves_cross_terms_and_fd():
    a,b,c0,c1,mount,*_ = setup()
    cov = sigma()
    out = evaluate(covariance=cov)
    relative = c0.matrix_body_to_ecef.T@c1.matrix_body_to_ecef
    points = np.r_[a.positions_m.ravel(),b.positions_m.ravel()]
    def res(delta):
        q = (points+delta).reshape(4,3)
        return mount@(q[0]-q[1])-relative@mount@(q[2]-q[3])
    j = fd(res,12)
    np.testing.assert_allclose(out.endpoint_jacobian,j,atol=8e-10)
    np.testing.assert_allclose(out.residual_covariance_m2, j@cov@j.T,rtol=2e-9,atol=1e-13)
    diagonal = evaluate(covariance=np.diag(np.diag(cov)))
    assert np.linalg.norm(diagonal.residual_covariance_m2-out.residual_covariance_m2)>1e-6


def test_common_mode_psd_noise_cancels_without_covariance_floor():
    # The same error added to all feet at each endpoint, with cross-time correlation.
    common = np.tile(np.eye(3),(4,1))
    out = evaluate(covariance=common@np.diag([1e-4,2e-4,3e-4])@common.T)
    np.testing.assert_allclose(out.residual_covariance_m2,0,atol=1e-30)
    zero = evaluate(covariance=np.zeros((12,12)))
    assert np.array_equal(zero.residual_covariance_m2,np.zeros((3,3)))


def test_flu_frame_and_endpoint_array_order_preserve_four_point_contract():
    a,b,c0,c1,*_ = setup()
    f=np.diag([1.,-1.,-1.])
    transformed_cov=np.kron(np.eye(4),f)@sigma()@np.kron(np.eye(4),f)
    new0=epoch(a.positions_m@f, a.time_s, frame="FLU")
    new1=epoch((b.positions_m@f)[::-1], b.time_s, ids=IDS[::-1], frame="FLU")
    changed=evaluate(new0,new1,c0,c1,covariance=transformed_cov)
    old=evaluate()
    for name in ("residual_body0_m","residual_covariance_m2","jacobian_world_current_clone"):
        np.testing.assert_allclose(getattr(changed,name),getattr(old,name),atol=1e-16)


def test_reversing_ordered_pair_changes_sign_not_covariance():
    old=evaluate()
    indices=np.r_[3:6,0:3,9:12,6:9]
    changed=evaluate(foot_pair=IDS[::-1], covariance=sigma()[np.ix_(indices,indices)])
    np.testing.assert_allclose(changed.residual_body0_m,-old.residual_body0_m,atol=1e-15)
    np.testing.assert_allclose(changed.jacobian_world_current_clone,-old.jacobian_world_current_clone,atol=1e-15)
    np.testing.assert_allclose(changed.residual_covariance_m2,old.residual_covariance_m2,atol=1e-19)


def test_rank2_and_common_world_rotation_gauge_hold_off_manifold():
    a,b,c0,c1,*_=setup()
    c1=attitude(exp([.4,.1,-.3])@c1.matrix_body_to_ecef,b.time_s)
    out=evaluate(a,b,c0,c1)
    assert np.linalg.norm(out.residual_body0_m)>.05 and out.joint_linearization_rank==2
    h=out.jacobian_world_current_clone
    np.testing.assert_allclose(h@np.vstack((np.eye(3),np.eye(3))),0,atol=0)
    np.testing.assert_allclose(h[:,:3]@out.current_null_axis_ecef,0,atol=1e-16)
    np.testing.assert_allclose(h[:,3:]@out.clone_null_axis_ecef,0,atol=1e-16)
    global_rotation=exp([.6,-.8,.4])
    changed=evaluate(a,b,attitude(global_rotation@c0.matrix_body_to_ecef,a.time_s),
                     attitude(global_rotation@c1.matrix_body_to_ecef,b.time_s))
    np.testing.assert_allclose(changed.residual_body0_m,out.residual_body0_m,atol=5e-16)
    np.testing.assert_allclose(changed.residual_covariance_m2,out.residual_covariance_m2,atol=1e-19)


def test_zero_and_numerically_degenerate_separation_fail_closed():
    a,b,*_=setup()
    for separation in (0.,1e-12):
        points=a.positions_m.copy(); points[1]=points[0]+[separation,0,0]
        with pytest.raises(FootPairDirectionError,match="degenerate"):
            evaluate(replace(a,positions_m=points))


def test_contact_id_stance_and_whole_interval_required():
    a,b,*_=setup()
    bads=[replace(b,contact_tokens=("new",b.contact_tokens[1])),
          replace(b,contact_tokens=(None,b.contact_tokens[1])),
          replace(b,stance=(False,True))]
    for bad in bads:
        with pytest.raises(FootPairDirectionError):evaluate(a,bad)
    for support in ({IDS[0]:True}, {IDS[0]:True,IDS[1]:None}, dict.fromkeys(IDS,False)):
        with pytest.raises(FootPairDirectionError):evaluate(interval_continuous_support=support)
    with pytest.raises(FootPairDirectionError):evaluate(foot_pair=("FL","missing"))
    with pytest.raises(FootPairDirectionError):evaluate(foot_pair=("FL","FL"))


def test_time_binding_availability_and_consumed_endpoint_checks():
    a,b,c0,c1,*_=setup()
    late=replace(c0,available_time_s=1.4)
    assert evaluate(a,b,late,c1).decision_available_time_s==1.4
    with pytest.raises(FootPairDirectionError,match="unavailable"):
        evaluate(a,b,late,c1,decision_time_s=1.3)
    with pytest.raises(FootPairDirectionError,match="exactly"):
        evaluate(a,b,replace(c0,time_s=.9),c1)
    with pytest.raises(FootPairDirectionError,match="increasing"):evaluate(a,a,c0,c0)
    for ids,consumed in [(("same","same"),()), (("raw:001","raw:002"),("raw:002",))]:
        with pytest.raises(FootPairDirectionError,match="repeated"):
            evaluate(endpoint_ids=ids,consumed_endpoint_ids=consumed)
    assert evaluate(position_gnss_input_used=False).position_gnss_input_used is False
    assert evaluate(position_gnss_input_used=True).position_gnss_input_used is True


def test_invalid_inputs_rejected_and_result_arrays_immutable():
    a,b,c0,c1,*_=setup()
    for rotation in (np.diag([1.,1.,-1.]),np.eye(3)*1.1,np.full((3,3),np.nan)):
        with pytest.raises(FootPairDirectionError):attitude(rotation,1.)
        with pytest.raises(FootPairDirectionError):evaluate(foot_frd_to_attitude_body=rotation)
    for cov in (-np.eye(12), np.eye(11),np.full((12,12),np.nan),np.eye(12)+np.eye(12,k=1)):
        with pytest.raises(FootPairDirectionError):evaluate(covariance=cov)
    for declaration in ("unknown",0):
        with pytest.raises(FootPairDirectionError):evaluate(position_gnss_input_used=declaration)
    with pytest.raises(FootPairDirectionError):evaluate(position_source_id="")
    with pytest.raises(FootPairDirectionError):
        direction_jacobian_current_ned(evaluate(),ecef_from_current_ned=np.eye(3),
                                      ned_frame_connection_per_m=np.ones((2,3)))
    out=evaluate()
    with pytest.raises(ValueError):out.residual_body0_m[0]=12.
    with pytest.raises(ValueError):c0.matrix_body_to_ecef[0,0]=2.


def test_positive_left_reset_fd_independent_exp_log():
    for a in (np.array([.35,-.2,.45]), np.array([1.4,-.7,.3]),np.array([math.pi-1e-3,0.,0.])):
        def reset(epsilon):
            return (Rotation.from_rotvec(a+epsilon)*Rotation.from_rotvec(-a)).as_rotvec()
        np.testing.assert_allclose(left_feedback_reset_jacobian(a),fd(reset,3),atol=2e-9)


def test_reset_zero_small_angle_sign_and_domain():
    assert np.array_equal(left_feedback_reset_jacobian([0.,0.,0.]),np.eye(3))
    small=left_feedback_reset_jacobian([0.,0.,1e-9])
    assert small[1,0]>0 and small[0,1]<0
    np.testing.assert_allclose(small[1,0],.5e-9,rtol=1e-14)
    for a in ([np.pi,0.,0.],[np.nan,0.,0.],[np.inf,0.,0.],[1.,2.]):
        with pytest.raises(FootPairDirectionError):left_feedback_reset_jacobian(a)
