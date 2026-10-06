"""Isolated physical/math oracles. No saved real models or integer searches."""
import json
import math
import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase.candidate_envelope import CircularArc
from legsa_gins.paper_rebuild.carrier_phase.sphere_cap_envelope import (
    sphere_direction_envelope,cover_from_arcs,intersect_covers)

P=np.array([[1.,0,0],[0,1.,0]])
LEDGER={'kernel_calls':0,'physical_ellipse_points':0,'physical_sphere_points':0}


def call(c,C,rho=1.,length=(.35,.35),axes=P,**kw):
    LEDGER['kernel_calls']+=1
    return sphere_direction_envelope(c,C,rho,horizontal_axes=axes,length_interval_m=length,**kw)


@pytest.fixture(scope='session',autouse=True)
def receipt():
    yield
    print('SPHERE_CAP_TEST_LEDGER='+json.dumps(LEDGER,sort_keys=True))


def test_01_anisotropic_ellipse_tangent_beats_old_disk():
    c=np.array([.35,0.,0.]);C=np.diag([.04**2,.002**2,.03**2])
    r=call(c,C)
    old=2*math.asin(.04/.35)
    exact=2*math.atan(.002/math.sqrt(.35**2-.04**2))
    assert exact<=r.ellipse_cover.total_width_rad<=exact+1e-7
    assert r.ellipse_cover.total_width_rad<old/10


def test_02_sphere_cap_shrinks_horizontal_disk():
    r=call([.5,0.,0.],np.eye(3)*.16**2)
    k=(.35**2+.5**2-.16**2)/(2*.35*.5)
    assert 2*math.acos(k)<=r.sphere_cap_cover.total_width_rad<=2*math.acos(k)+1e-7
    assert r.cover.total_width_rad < 2*math.asin(.16/.5)


def test_03_exact_length_empty_and_tangent_guard():
    empty=call([.6,0.,0.],np.eye(3)*.1**2)
    assert empty.status=='EMPTY_NECESSARY_GEOMETRY'
    tangent=call([.45,0.,0.],np.eye(3)*.1**2)
    assert not tangent.cover.empty and tangent.cover.contains(0.)


def test_04_center_origin_has_full_yaw_or_empty_sphere():
    a=call([0.,0.,0.],np.eye(3)*.4**2)
    b=call([0.,0.,0.],np.eye(3)*.3**2)
    assert a.cover.full_circle
    assert b.cover.empty


def test_05_vertical_pole_contained_is_full_yaw():
    r=call([.01,0.,.35],np.eye(3)*.02**2)
    assert r.sphere_cap_contains_pole and r.cover.full_circle
    # A pole can be inside a cap even when the center has nonzero horizontal norm.
    assert r.horizontal_ellipse_origin_included


def test_06_wrap_and_two_disconnected_components_are_kept():
    a=cover_from_arcs((CircularArc(math.radians(-170),math.radians(340)),))
    b=cover_from_arcs((CircularArc(math.radians(10),math.radians(340)),))
    out=intersect_covers(a,b)
    assert len(out.components)==2
    assert abs(math.degrees(out.total_width_rad)-320)<1e-9
    for deg in (-150,-20,20,150):assert out.contains(math.radians(deg))
    for deg in (0,180):assert not out.contains(math.radians(deg))
    wrap=call([-.35,0.,0.],np.eye(3)*.01**2)
    assert wrap.cover.contains(math.pi) and wrap.cover.contains(-math.pi)


def test_07_near_touch_does_not_turn_into_spurious_empty():
    a=cover_from_arcs((CircularArc(-.1,.1),))
    b=cover_from_arcs((CircularArc(1e-12,.1),))
    out=intersect_covers(a,b)
    assert not out.empty and out.contains(0.)
    far=cover_from_arcs((CircularArc(.01,.1),))
    assert intersect_covers(a,far).empty


def test_08_zero_budget_nonvertical_point_and_vertical_undefined():
    r=call([.35,0.,0.],np.eye(3),rho=0)
    assert r.cover.contains(0.) and r.cover.total_width_rad<1e-6
    vertical=call([0.,0.,.35],np.eye(3),rho=0)
    assert vertical.cover.full_circle


def test_09_frame_rotation_preserves_entire_cover():
    axis=np.array([1.,2.,3.]);axis/=np.linalg.norm(axis)
    K=np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]])
    R=np.eye(3)+math.sin(.7)*K+(1-math.cos(.7))*K@K
    c=np.array([.34,.03,.02]);C=np.array([[.001,.0001,0],[.0001,.0004,.00005],[0,.00005,.0008]])
    a=call(c,C);b=call(R@c,R@C@R.T,axes=P@R.T)
    assert abs(a.cover.total_width_rad-b.cover.total_width_rad)<1e-10
    assert abs(a.cover.enclosing_arc.center_rad-b.cover.enclosing_arc.center_rad)<1e-10


def test_10_coordinate_scale_preserves_cover():
    c=np.array([.34,.03,.02]);C=np.diag([.02**2,.04**2,.025**2])
    a=call(c,C)
    for factor in (1e-6,1e6):
        b=call(factor*c,factor*factor*C,length=(.35*factor,.35*factor))
        assert abs(a.cover.total_width_rad-b.cover.total_width_rad)<1e-10


def test_11_independent_horizontal_ellipse_points_contained():
    c=np.array([.35,.02,.04]);M=np.array([[.035,.009,0],[.002,.007,.002],[0,.005,.02]])
    C=M@M.T;r=call(c,C,rho=2.)
    L=np.linalg.cholesky(P@C@P.T)
    for i in range(128):
        theta=2*math.pi*(i+.5)/128
        h=P@c+math.sqrt(2.)*L@np.array([math.cos(theta),math.sin(theta)])
        LEDGER['physical_ellipse_points']+=1
        assert r.ellipse_cover.contains(math.atan2(h[1],h[0]),tolerance=1e-12)


def test_12_independent_known_length_sphere_points_contained():
    c=np.array([.34,.001,.01]);C=np.diag([.02**2,.04**2,.025**2])
    r=call(c,C,rho=4.)
    for i in range(128):
        yaw=-.15+.3*(i+.5)/128
        elevation=.08*math.sin(7*i)
        b=.35*np.array([math.cos(elevation)*math.cos(yaw),math.cos(elevation)*math.sin(yaw),math.sin(elevation)])
        assert (b-c)@np.linalg.solve(C,b-c)<4.  # independent physical membership
        LEDGER['physical_sphere_points']+=1
        assert r.ellipse_cover.contains(yaw,tolerance=1e-12)
        assert r.sphere_cap_cover.contains(yaw,tolerance=1e-12)
        assert r.cover.contains(yaw,tolerance=1e-12)


def test_13_registered_shell_uses_interior_stationary_minimum():
    # s=.5,r=.3 => stationary length=.4 inside [.3,.6].
    shell=call([.5,0.,0.],np.eye(3)*.3**2,length=(.3,.6))
    assert abs(shell.cap_cosine_lower_bound-.8)<1e-8
    assert shell.sphere_cap_cover.contains(math.asin(.6),tolerance=1e-9)
    fixed_wrong=call([.5,0.,0.],np.eye(3)*.01**2,length=(.35,.35))
    assert fixed_wrong.cover.empty  # wrong length can exclude a valid .5-m truth


def test_14_negative_budget_and_bad_covariance_fail_closed():
    r=call([.35,0.,0.],np.eye(3),rho=-.01)
    assert r.status=='EMPTY_RAW_DOMAIN'
    with pytest.raises(ValueError):call([.35,0.,0.],np.diag([1.,-1.,1.]))
    with pytest.raises(ValueError):call([.35,0.,0.],np.diag([1.,1e-15,1.]))


def test_15_legacy_cover_is_intersected_not_replaced_by_center():
    old=cover_from_arcs((CircularArc(-.005,.01),))
    r=call([.35,0.,0.],np.eye(3)*.02**2,legacy_cover=old)
    assert r.cover.total_width_rad<=.01+1e-12 and r.cover.contains(0.)


def test_16_input_arrays_are_not_changed_and_recorded_radius_is_not_shrunk():
    c=np.array([.35,0.,0.]);C=np.eye(3)*.01**2;axes=P.copy()
    original=(c.copy(),C.copy(),axes.copy())
    r=call(c,C,axes=axes,recorded_outer_radius_m=.02)
    assert r.three_dimensional_outer_radius_m==.02
    for before,after in zip(original,(c,C,axes)):assert np.array_equal(before,after)
