"""Twelve fixed synthetic qualification cases; no real inputs or native calls."""
import json
import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase import arc_phase_information as info
from legsa_gins.paper_rebuild.carrier_phase import attitude_clone as clone


def call(p, h, r, *, mode=info.ZERO_CROSS, c=None, w=None, gauge=None, **changes):
    kwargs=dict(mode=mode, covariance_kind="SECOND_MOMENT_UPPER_BOUND" if mode==info.UNKNOWN_CROSS else "WORKING_COVARIANCE",
                error_model="SECOND_MOMENT_ABOUT_NOMINAL" if mode==info.UNKNOWN_CROSS else "CENTERED_ZERO_MEAN_GIVEN_INFORMATION",
                conditioning_information_id="FIXED_SYNTHETIC_INFORMATION_SET", prior_source_id="SYNTHETIC_JOINT_PRIOR",
                measurement_source_id="SYNTHETIC_NOISE", cross_source_id="EXPLICIT_SYNTHETIC_CROSS_CONTRACT",
                qualification_note="Synthetic working model; no physical qualification",
                objective_weights=np.eye(6) if w is None else w, objective_source_id="FROZEN_SYNTHETIC_W",
                endpoint_times_s=(0., .8), C_en=c, gauge_basis=gauge, actual_available_time_s=None)
    kwargs.update(changes)
    return info.diagnose(p,h,r,**kwargs)


def oracle(p,h,r,c):
    pp=np.eye(21);pp[:6,:6]=p
    hh=np.zeros((len(h),21));hh[:,:6]=h
    cc=np.zeros((21,len(h)));cc[:6]=c
    state=clone.ErrorGaussian(np.zeros(21),pp,1.,"SYNTHETIC_ORACLE")
    correlation=clone.NoiseCorrelation(clone.SUPPLIED_CROSS,"SYNTHETIC_CROSS","known only for this toy",cc)
    post,_=clone.update_measurement(state,np.zeros(len(h)),hh,r,correlation=correlation,
        measurement_id="ONE_SYNTHETIC_MEASUREMENT",measurement_time_s=1.,available_time_s=1.)
    return post.covariance[:6,:6]


def rotation(v):
    theta=np.linalg.norm(v)
    if theta==0:return np.eye(3)
    x,y,z=v/theta;k=np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
    return np.eye(3)+np.sin(theta)*k+(1-np.cos(theta))*(k@k)


def dense_case():
    rng=np.random.default_rng(731)
    a=rng.normal(size=(6,6));p=a@a.T+.5*np.eye(6)
    h=rng.normal(size=(3,6));r=np.diag([1.,2.,3.])
    u=rng.normal(size=(6,3));u*=.4/np.linalg.norm(u,2)
    c=np.linalg.cholesky(p)@u@np.linalg.cholesky(r).T
    return p,h,r,c


def test_01_so3_jacobian_and_baseline_spin_gauge():
    g0=np.array([[1.,0.,.4],[.2,1.,0.],[-.3,.5,1.],[.8,-.5,.1]])
    g1=g0+np.array([[.01,0.,0.],[0.,-.02,0.],[0.,0.,.03],[.01,.02,-.01]])
    c0=rotation(np.array([.1,-.2,.3]));c1=rotation(np.array([-.2,.1,.4]));b=np.array([0.,.28,0.])
    model=info.linearize_geometry(g0,g1,c0,c1,b);h=model['H'];finite=np.zeros_like(h);eps=1e-7
    for i in range(6):
        e=np.zeros(3);e[i%3]=eps
        pp=info.linearize_geometry(g0,g1,rotation(e)@c0 if i<3 else c0,rotation(e)@c1 if i>=3 else c1,b)['prediction_m']
        pm=info.linearize_geometry(g0,g1,rotation(-e)@c0 if i<3 else c0,rotation(-e)@c1 if i>=3 else c1,b)['prediction_m']
        finite[:,i]=(pp-pm)/(2*eps)
    np.testing.assert_allclose(h,finite,atol=1e-9,rtol=1e-8)
    np.testing.assert_allclose(h@model['baseline_spin_gauge'],0.,atol=1e-15)
    assert np.linalg.matrix_rank(h)<=4


def test_02_static_common_rotation_gauge_is_preserved():
    model=info.linearize_geometry(np.eye(3),np.eye(3),np.eye(3),np.eye(3),[0.,.28,0.])
    common=np.vstack((np.eye(3),np.eye(3)))/np.sqrt(2.)
    np.testing.assert_allclose(model['H']@common,0.,atol=1e-15)
    result=call(np.eye(6),model['H'],.01*np.eye(3),gauge=common)
    np.testing.assert_allclose(common.T@np.asarray(result['P_posterior'])@common,np.eye(3),atol=1e-14)
    assert result['posterior_projected_traces']['relative_ecef']<3.
    assert not result['navigation_admitted']


def test_03_numerical_rank_does_not_establish_information_size():
    g0=np.vstack((np.eye(3),np.eye(3)))
    g1=g0+1e-4*np.vstack((np.eye(3),-np.eye(3)))
    flat=info.linearize_geometry(g0,g0,np.eye(3),np.eye(3),[0.,.28,0.])
    moving=info.linearize_geometry(g0,g1,np.eye(3),np.eye(3),[0.,.28,0.])
    assert np.linalg.matrix_rank(flat['H'])==2 and np.linalg.matrix_rank(moving['H'])==4
    result=call(np.eye(6),moving['H'],1e8*np.eye(6))
    assert max(result['working_information_eigenvalues'])<1e-8
    assert np.trace(np.asarray(result['covariance_reduction']))<1e-8
    common=np.vstack((np.eye(3),np.eye(3)))/np.sqrt(2.)
    common_direct=common.T@np.asarray(result['direct_geometry_information'])@common
    assert np.trace(common_direct)<1e-15


def test_04_complete_temporal_cross_changes_increment():
    p=np.block([[np.eye(3),.999*np.eye(3)],[.999*np.eye(3),np.eye(3)]])
    h=np.hstack((-np.eye(3),np.eye(3)));r=.01*np.eye(3)
    coupled=call(p,h,r);independent=call(np.eye(6),h,r)
    assert np.trace(coupled['covariance_reduction'])<.001*np.trace(independent['covariance_reduction'])
    with pytest.raises(info.InformationError):call([np.eye(3),np.eye(3)],h,r)


def test_05_zero_cross_scalar_formula_and_existing_oracle():
    p=np.diag([4.,1.,1.,1.,1.,1.]);h=np.zeros((1,6));h[0,0]=2.;r=np.array([[3.]])
    result=call(p,h,r);post=np.asarray(result['P_posterior'])
    assert post[0,0]==pytest.approx(12/19)
    np.testing.assert_allclose(post,oracle(p,h,r,np.zeros((6,1))),atol=1e-14)
    assert result['physical_independence_proven'] is False


def test_06_supplied_dense_cross_full_conditional_and_joseph_oracle():
    p,h,r,c=dense_case()
    for sign in (-1.,1.):
        result=call(p,h,r,mode=info.SUPPLIED_CROSS,c=sign*c)
        s=h@p@h.T+r+h@(sign*c)+(sign*c).T@h.T
        v=p@h.T+sign*c
        conditional=p-v@np.linalg.solve(s,v.T)
        np.testing.assert_allclose(result['P_posterior'],conditional,atol=2e-13,rtol=1e-12)
        np.testing.assert_allclose(result['P_posterior'],oracle(p,h,r,sign*c),atol=2e-13,rtol=1e-12)
        assert result['physical_cross_qualification_proven'] is False


def test_07_cancellation_cross_has_no_new_information():
    p=np.eye(6);h=np.hstack((np.eye(3),2*np.eye(3)));c=-p@h.T;r=h@p@h.T+np.eye(3)
    result=call(p,h,r,mode=info.SUPPLIED_CROSS,c=c)
    np.testing.assert_array_equal(result['gain'],np.zeros((6,3)))
    np.testing.assert_array_equal(result['P_posterior'],p)
    np.testing.assert_array_equal(result['covariance_reduction'],np.zeros((6,6)))
    falsely_independent=call(p,h,r)
    assert np.trace(falsely_independent['covariance_reduction'])>0


def test_08_unknown_cross_full_bound_and_continuous_existence():
    p,h,r,_=dense_case();result=call(p,h,r,mode=info.UNKNOWN_CROSS)
    rng=np.random.default_rng(20261007)
    for _ in range(16):
        u=rng.normal(size=(6,3));u*=.95/np.linalg.norm(u,2)
        c=np.linalg.cholesky(p)@u@np.linalg.cholesky(r).T
        for row in result['unknown_objectives']['joint']['grid']:
            eps=row['epsilon'];k=np.linalg.solve(h@p@h.T+r/eps,h@p).T;f=np.eye(6)-k@h
            actual=f@p@f.T+k@r@k.T-f@c@k.T-k@c.T@f.T
            difference=np.asarray(row['bound'])-actual
            assert np.linalg.eigvalsh((difference+difference.T)/2)[0]>=-2e-10
    strong=np.hstack((4*np.eye(3),np.zeros((3,3))))
    q=call(np.eye(6),strong,np.eye(3),mode=info.UNKNOWN_CROSS)['unknown_objectives']['joint']
    assert q['T']==6. and q['J']==48. and q['continuous_improvement_exists'] is True
    eps=1e-6;k=np.linalg.solve(strong@strong.T+np.eye(3)/eps,strong).T;f=np.eye(6)-k@strong
    assert np.trace((1+eps)*(f@f.T+k@k.T/eps))<q['T']
    assert result['P_posterior'] is None and result['conditional_independence_result'] is None


def test_09_singular_joint_prior_and_singular_innovation_no_loading():
    p=np.block([[np.eye(3),np.eye(3)],[np.eye(3),np.eye(3)]]);h=np.hstack((-np.eye(3),np.eye(3)))
    result=call(p,h,np.eye(3))
    np.testing.assert_allclose(result['P_posterior'],p,atol=0.)
    single=np.zeros((1,6));single[0,0]=1.
    with pytest.raises(info.InformationError,match='INNOVATION_NOT_SPD_NO_LOADING'):
        call(np.eye(6),single,np.ones((1,1)),mode=info.SUPPLIED_CROSS,c=-single.T)


def test_10_tiny_positive_variance_weight_mass_is_not_discarded():
    p=np.diag([1.,1e-16,0.,0.,0.,0.]);w=np.diag([1.,1e16,0.,0.,0.,0.])
    result=call(p,np.zeros((1,6)),np.ones((1,1)),mode=info.UNKNOWN_CROSS,w=w)
    q=result['unknown_objectives']['declared']
    assert q['T']==2. and q['J']==0. and q['omega_zero_score']==2.
    assert q['continuous_condition']=='CONTINUOUS_NO_IMPROVEMENT' and q['grid_selected_epsilon']==0.
    assert all(row['score']>2. for row in q['grid'])
    json.dumps(result,allow_nan=False)


def test_11_rotated_and_rescaled_coordinates_preserve_full_objective():
    p,h,r,c=dense_case();w=np.diag([1.,2.,3.,4.,5.,6.])
    rot=rotation(np.array([.3,-.4,.1]));q=np.zeros((6,6));q[:3,:3]=rot;q[3:,3:]=rot
    d=np.diag([1e8,1e-8,2.,3.,.5,1.])@q;di=np.linalg.inv(d)
    for mode in (info.SUPPLIED_CROSS,info.UNKNOWN_CROSS):
        a=call(p,h,r,mode=mode,c=c if mode==info.SUPPLIED_CROSS else None,w=w)
        b=call(d@p@d.T,h@di,r,mode=mode,c=d@c if mode==info.SUPPLIED_CROSS else None,w=di.T@w@di)
        if mode==info.SUPPLIED_CROSS:
            np.testing.assert_allclose(di@np.asarray(b['P_posterior'])@di.T,a['P_posterior'],atol=1e-10,rtol=1e-9)
            assert b['declared_objective_posterior']==pytest.approx(a['declared_objective_posterior'],rel=1e-10)
        else:
            aa=a['unknown_objectives']['declared'];bb=b['unknown_objectives']['declared']
            assert bb['T']==pytest.approx(aa['T'],rel=1e-10) and bb['J']==pytest.approx(aa['J'],rel=1e-10)
            np.testing.assert_allclose([x['score'] for x in aa['grid']],[x['score'] for x in bb['grid']],rtol=1e-10)
        np.testing.assert_allclose(a['working_information_eigenvalues'],b['working_information_eigenvalues'],atol=1e-11,rtol=1e-10)


def test_12_source_domain_and_unknown_availability_contracts():
    p=np.eye(6);h=np.ones((1,6));r=np.ones((1,1))
    bad=[dict(mode=''),dict(conditioning_information_id=''),dict(objective_source_id=''),
         dict(covariance_kind='SECOND_MOMENT_UPPER_BOUND'),dict(error_model='UNKNOWN'),
         dict(actual_available_time_s=.7),dict(endpoint_times_s=(1.,0.)),dict(c=np.zeros((6,1)))]
    for changes in bad:
        with pytest.raises(info.InformationError):call(p,h,r,**changes)
    with pytest.raises(info.InformationError):call(p,h,r,mode=info.SUPPLIED_CROSS,c=100*np.ones((6,1)))
    with pytest.raises(info.InformationError):call(p,h,r,mode=info.SUPPLIED_CROSS)
    with pytest.raises(info.InformationError):call(p*np.nan,h,r)
    with pytest.raises(info.InformationError):call(p,h,np.zeros((1,1)))
    for mode in (info.ZERO_CROSS,info.UNKNOWN_CROSS):
        with pytest.raises(info.InformationError,match="UNRESOLVED"):
            call(p,np.full((1,6),1e200),r,mode=mode)
        with pytest.raises(info.InformationError,match="UNRESOLVED"):
            call(1e200*p,np.zeros((1,6)),r,mode=mode,w=1e200*p)
    valid=call(p,h,r)
    assert valid['actual_available_time_s'] is None and not valid['navigation_admitted']
    assert valid['conditioning_information_id']=='FIXED_SYNTHETIC_INFORMATION_SET'
