"""Low-dimensional synthetic support tests; no real data/native search/navigation."""
import itertools
import json
import math
from dataclasses import replace
import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import (
    CircularArc, enclosing_arc, enumerate_candidate_envelope)
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock, TemporalModelError, assemble_epochs

AXES = np.array([[1.,0.,0.],[0.,1.,0.]])
CALLS = []


def run(problem, threshold, **kwargs):
    record = {'status':'RAISED_BEFORE_RESULT'}
    CALLS.append(record)
    result = enumerate_candidate_envelope(problem,threshold,lambda_library=None,
        horizontal_axes=AXES,**kwargs)
    record.update(status=result.status,nodes=result.expanded_nodes,leaves=result.integer_leaves)
    return result


@pytest.fixture(scope='session',autouse=True)
def enumeration_receipt():
    yield
    print('\nCANDIDATE_ENVELOPE_LOCAL_RECEIPT '+json.dumps({
        'enumeration_api_calls':len(CALLS),'returned_results':sum('nodes' in x for x in CALLS),
        'expanded_nodes':sum(x.get('nodes',0) for x in CALLS),
        'integer_leaves':sum(x.get('leaves',0) for x in CALLS),
        'status_counts':{s:sum(x['status']==s for x in CALLS) for s in sorted({x['status'] for x in CALLS})},
        'lambda_native_calls':0,'raw_reads':0,'navigation_calls':0},sort_keys=True))


def analytic_problem(mean_n, center, covariance):
    # Abstract full-rank linear model X=I. Its Gaussian ellipsoid is analytic;
    # this is not claimed to be a real signal geometry or a fixed-length solution.
    mean_n = np.atleast_1d(mean_n).astype(float)
    m = len(mean_n)
    x = np.eye(m+3)
    block = EpochBlock(1.,np.r_[mean_n,center],x[:,:m],x[:,m:],covariance,
                       tuple(f'N{i}' for i in range(m)),{'baseline_frame':'ECEF'})
    return assemble_epochs([block])


def test_two_dimensional_full_covariance_support_matches_finite_exact_oracle():
    qaa = np.array([[.3,.12],[.12,.2]])
    gain = np.array([[.03,-.02],[.01,.005],[0.,.01]])
    cb = np.diag([.0002,.0003,.0004])
    q = np.block([[qaa,qaa@gain.T],[gain@qaa,cb+gain@qaa@gain.T]])
    ahat = np.array([.15,-.2])
    p = analytic_problem(ahat,[.35,.04,.01],q)
    result = run(p,5.)
    oracle = {n for n in itertools.product(range(-3,4),repeat=2)
              if (np.array(n)-ahat)@np.linalg.solve(qaa,np.array(n)-ahat) <= 5.}
    # Coordinate ellipsoid bounds prove the [-3,3] oracle contains the entire domain.
    assert np.all(abs(ahat)+np.sqrt(5*np.diag(qaa)) < 3)
    assert {c.integer for c in result.candidates} == oracle
    assert result.numerical_support_complete
    for c in result.candidates:
        np.testing.assert_allclose(c.baseline_center_m,np.array([.35,.04,.01])+gain@(np.array(c.integer)-ahat),atol=1e-14)
    assert not result.rigorous_interval_certificate and not result.integer_acceptance_defined


def test_physical_dd_shared_pivot_covariance_and_known_integer():
    lam = 299792458./1575420000.
    pivot = np.array([0.,0.,1.])
    targets = np.array([[.8,0.,.6],[0.,.8,.6],[-.6,0.,.8]])
    h = pivot-targets
    assert np.linalg.matrix_rank(h) == 3
    b = np.array([.2,.1,math.sqrt(.35**2-.2**2-.1**2)])
    n = np.array([3,-2,1])
    differencing = np.c_[np.eye(3),-np.ones(3)]
    u = np.zeros((6,8));u[:3,:4]=differencing;u[3:,4:]=differencing
    factor = np.diag([.002]*4+[.00002]*4)
    factor[5,0] = .000002
    qsd = factor@factor.T
    q = u@qsd@u.T
    a = np.vstack([np.zeros((3,3)),lam*np.eye(3)])
    B = np.vstack([h,h])
    block = EpochBlock(2.,a@n+B@b,a,B,q,('a','b','c'),{'baseline_frame':'ECEF'})
    p = assemble_epochs([block])
    result = run(p,1.)
    assert result.numerical_support_complete
    assert [c.integer for c in result.candidates] == [tuple(n)]
    np.testing.assert_allclose(result.candidates[0].baseline_center_m,b,atol=2e-13)
    # Independent conditional GLS on the full Q, not a diagonal noise surrogate.
    wi = np.linalg.inv(q)
    cb = np.linalg.inv(B.T@wi@B)
    expected_radius = math.sqrt(np.linalg.eigvalsh(AXES@cb@AXES.T)[-1])
    assert result.candidates[0].horizontal_outer_radius_m == pytest.approx(expected_radius,rel=1e-6)


def test_third_integer_can_have_opposite_heading_to_first_two():
    # N centers 0 and 1 point +x, but the third-cost N=-1 points -x.
    qaa = .4
    gain = np.array([.19,0.,0.])
    cb = np.diag([1e-6,1e-8,1e-8])
    q = np.block([[np.array([[qaa]]),qaa*gain[None,:]],
                  [qaa*gain[:,None],cb+qaa*np.outer(gain,gain)]])
    result = run(analytic_problem([.1],[.12,0.,0.],q),3.1)
    ordered = sorted(result.candidates,key=lambda c:c.gaussian_integer_cost)
    assert [c.integer for c in ordered] == [(0,),(1,),(-1,)]
    assert all(c.baseline_center_m[0] > 0 for c in ordered[:2])
    assert ordered[2].baseline_center_m[0] < 0
    assert result.azimuth_outer_arc.width_rad > math.pi


def test_single_integer_envelope_includes_continuous_angle_crossing():
    q = np.diag([1e-4,.0001,.0025,.0001])
    result = run(analytic_problem([2.],[.35,0.,0.],q),1.)
    assert len(result.candidates) == 1
    c = result.candidates[0]
    assert c.azimuth_outer_arc.width_rad > .25
    # A feasible noncentral baseline has nonzero azimuth and must remain inside.
    b = np.array([.35,.04,0.])
    assert b@b != .35**2  # this test deliberately checks the free-baseline relaxation
    assert (b-np.array(c.baseline_center_m))@np.linalg.solve(q[1:,1:],b-np.array(c.baseline_center_m)) < 1
    assert contains(c.azimuth_outer_arc,math.atan2(b[1],b[0]))


def contains(arc,angle):
    if arc.full_circle:return True
    return (angle-arc.start_rad)%(2*math.pi) <= arc.width_rad+1e-12


def test_negative_axis_wrap_does_not_create_artificial_full_circle():
    result = run(analytic_problem([0.],[-.35,0.,0.],np.diag([1e-4,1e-4,1e-4,1e-4])),1.)
    arc = result.azimuth_outer_arc
    assert arc.width_rad < .1
    assert contains(arc,math.pi-.01) and contains(arc,-math.pi+.01)
    assert not contains(arc,0.)


def test_union_wrap_and_contained_arcs_use_covered_endpoints():
    arcs = [CircularArc(math.radians(178),math.radians(4)),
            CircularArc(math.radians(-179),math.radians(3)),
            CircularArc(math.radians(179),math.radians(1))]
    cover = enclosing_arc(arcs)
    assert cover.width_rad == pytest.approx(math.radians(6),abs=1e-12)
    for arc in arcs:
        for f in [0.,.25,.5,.75,1.]:assert contains(cover,arc.start_rad+f*arc.width_rad)


@pytest.mark.parametrize('xy',[(0.,0.),(.0001,0.)])
def test_near_vertical_horizontal_origin_means_full_circle(xy):
    result = run(analytic_problem([0.],[*xy,.35],np.diag([1e-4,1e-4,1e-4,1e-4])),1.)
    assert result.candidates[0].horizontal_origin_included
    assert result.azimuth_outer_arc.full_circle


@pytest.mark.parametrize('kwargs,reason',[
    ({'node_limit':1},'NODE_LIMIT'),({'candidate_limit':1},'CANDIDATE_LIMIT'),
    ({'timeout_s':1e-300},'TIMEOUT')])
def test_limits_never_publish_complete_union(kwargs,reason):
    result = run(analytic_problem([0.],[.35,0.,0.],np.diag([1.,1e-4,1e-4,1e-4])),4.,**kwargs)
    assert result.termination_reason == reason
    assert not result.numerical_support_complete and result.azimuth_outer_arc is None


def test_exact_threshold_boundary_integers_are_included():
    result = run(analytic_problem([0.],[.35,0.,0.],np.diag([1.,1e-4,1e-4,1e-4])),1.)
    assert {c.integer for c in result.candidates} == {(-1,),(0,),(1,)}
    assert result.expanded_working_threshold > result.raw_cost_threshold


def test_empty_support_is_complete_but_not_a_heading():
    result = run(analytic_problem([.5],[.35,0.,0.],np.diag([.01,1e-4,1e-4,1e-4])),1.)
    assert result.numerical_support_complete and result.status == 'EMPTY_RELAXED_SUPPORT'
    assert result.candidates == () and result.azimuth_outer_arc is None


def test_ill_conditioned_float_fails_closed():
    result = run(analytic_problem([0.],[.35,0.,0.],np.diag([1.,1e-12,1e-12,1e-12])),1.,max_condition_number=100.)
    assert result.status == 'UNQUALIFIED_NUMERICS'
    assert not result.numerical_support_complete and result.azimuth_outer_arc is None


def test_rank_deficient_float_does_not_invent_coverage():
    p = analytic_problem([0.],[.35,0.,0.],np.eye(4))
    p = replace(p,A=np.zeros_like(p.A))
    result = run(p,1.)
    assert result.status == 'UNQUALIFIED_NUMERICS'


def test_full_cross_epoch_q_uses_marginal_continuous_enclosure():
    # Each epoch independently observes one shared integer and its baseline.
    a=np.array([[1.],[0.],[0.],[0.]])
    B=np.vstack([np.zeros((1,3)),np.eye(3)])
    q=np.diag([.01,.0004,.0009,.0016])
    b1=np.array([.35,0.,0.]);b2=np.array([.34,.05,0.])
    blocks=[EpochBlock(float(k+1),a[:,0]*2+B@b,a,B,q,('n',),{'baseline_frame':'ECEF'})
            for k,b in enumerate([b1,b2])]
    full=np.block([[q,.5*q],[.5*q,q]])
    p=assemble_epochs(blocks,temporal_covariance=full)
    result=run(p,1.)
    assert result.numerical_support_complete and len(result.candidates)==1
    np.testing.assert_allclose(result.candidates[0].baseline_center_m,b2,atol=1e-14)
    # Marginal conditional baseline variance .0009 remains; a conditional Schur
    # variance .75*.0009 would incorrectly shrink the last-epoch azimuth cover.
    assert result.candidates[0].horizontal_outer_radius_m == pytest.approx(.03,rel=1e-6)


def test_unimodular_decorrelation_path_with_nontrivial_mock_transform(monkeypatch):
    import legsa_gins.paper_rebuild.carrier_phase.candidate_envelope as mod
    q=np.diag([.4,.3,1e-4,1e-4,1e-4])
    problem=analytic_problem([.1,-.2],[.35,0.,0.],q)
    base=run(problem,4.)
    class Bridge:
        def __init__(self,path):assert path=='EXPLICIT_TEST_BRIDGE_NO_NATIVE'
        def decorrelate(self,a,q):
            class Reduced:transformation=np.array([[1,2],[0,1]])
            return Reduced()
    monkeypatch.setattr(mod,'RTKLIBLambdaBridge',Bridge)
    # This public call is also counted, but the mock never opens a native library.
    result=mod.enumerate_candidate_envelope(problem,4.,lambda_library='EXPLICIT_TEST_BRIDGE_NO_NATIVE',horizontal_axes=AXES)
    CALLS.append({'status':result.status,'nodes':result.expanded_nodes,'leaves':result.integer_leaves})
    assert result.numerical_support_complete
    assert {x.integer for x in result.candidates}=={x.integer for x in base.candidates}


def test_invalid_threshold_is_rejected_before_search():
    with pytest.raises(TemporalModelError):
        run(analytic_problem([0.],[.35,0.,0.],np.eye(4)),-1.)


# Stage-B optional whole-domain length filter: targeted tests only.
def test_length_filter_overlap_does_not_test_only_conditional_center():
    from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import filter_length_necessary_support
    p=analytic_problem([0.],[.41,0.,0.],np.diag([1e-4,.01,.01,.01]))
    envelope=run(p,1.)
    view=filter_length_necessary_support(p,envelope)
    assert view.necessary_support_complete and len(view.retained_candidates)==1
    assert view.items[0].checks[0].center_norm_m != pytest.approx(.35)
    assert view.items[0].checks[0].necessary_condition_passed
    assert len(envelope.candidates)==1  # raw result not mutated


def test_length_filter_uses_every_epoch_not_only_target_center():
    from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import filter_length_necessary_support
    a=np.array([[1.],[0.],[0.],[0.]])
    B=np.vstack([np.zeros((1,3)),np.eye(3)])
    q=np.diag([1e-4,1e-4,1e-4,1e-4])
    blocks=[EpochBlock(float(i),np.r_[0.,b],a,B,q,('n',),{'baseline_frame':'ECEF'})
            for i,b in enumerate([[.8,0.,0.],[.35,0.,0.]])]
    p=assemble_epochs(blocks)
    envelope=run(p,1.)
    view=filter_length_necessary_support(p,envelope)
    assert view.status=='EMPTY_NECESSARY_SUPPORT' and view.necessary_support_complete
    assert not view.items[0].checks[0].necessary_condition_passed
    assert view.items[0].checks[1].necessary_condition_passed
    assert view.azimuth_outer_arc is None


def test_length_filter_tangent_boundary_is_retained():
    from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import filter_length_necessary_support
    p=analytic_problem([0.],[.45,0.,0.],np.diag([1e-4,.01,.01,.01]))
    view=filter_length_necessary_support(p,run(p,1.))
    assert len(view.retained_candidates)==1


def test_length_filter_incomplete_domain_never_becomes_complete_empty():
    from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import filter_length_necessary_support
    p=analytic_problem([0.],[.8,0.,0.],np.diag([1.,1e-4,1e-4,1e-4]))
    view=filter_length_necessary_support(p,run(p,4.,candidate_limit=1))
    assert view.status=='INCOMPLETE_NECESSARY_SUPPORT'
    assert not view.raw_support_complete and not view.necessary_support_complete
    assert len(view.retained_candidates)==0 and view.azimuth_outer_arc is None


def test_length_filter_requires_same_numerical_problem():
    from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import filter_length_necessary_support
    p=analytic_problem([0.],[.35,0.,0.],np.diag([1e-4,.01,.01,.01]))
    envelope=run(p,1.)
    other=replace(p,y=p.y+np.array([0.,.01,0.,0.]))
    with pytest.raises(TemporalModelError,match='original bound envelope'):
        filter_length_necessary_support(other,envelope)


def test_length_filter_preserves_five_known_feasible_sphere_points():
    from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import filter_length_necessary_support
    truth=np.array([.21,.28,0.])
    assert np.linalg.norm(truth)==pytest.approx(.35)
    for displacement in ([.02,0.,0.],[-.04,.02,0.],[0.,0.,.1],[.1,-.03,.04],[-.01,-.01,-.01]):
        v=np.asarray(displacement)
        variance=2*float(v@v)
        p=analytic_problem([0.],truth-v,np.diag([1e-4,variance,variance,variance]))
        # Independent raw cost of the known length truth equals one half.
        assert (truth-(truth-v))@(truth-(truth-v))/variance==pytest.approx(.5)
        view=filter_length_necessary_support(p,run(p,1.))
        assert view.necessary_support_complete and len(view.retained_candidates)==1
