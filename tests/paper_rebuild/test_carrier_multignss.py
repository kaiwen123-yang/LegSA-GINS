"""Synthetic observable/geometry contracts; no real data or reference reads."""
from dataclasses import replace
import math

import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase import multignss as mg
from legsa_gins.paper_rebuild.carrier_phase.ephemeris import CheckedRtklibProvider
from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw
from legsa_gins.paper_rebuild.horizontal_literature.reproduction_backend import PairGeometry

GROUPS = ((0, 0, 0), (0, 3, 0), (2, 0, 0), (2, 5, 0), (3, 0, 0), (3, 2, 0))
BASELINE = np.array([0.12, -0.27, 0.19])
ANCHOR = np.array([6378137.0, 0., 0.])


def unit(sv):
    u = np.array([[.9, .1, .3], [.7, -.4, .5], [.5, .6, .4], [.3, -.2, .8]])[sv-1]
    return u / np.linalg.norm(u)


def fixture(groups=GROUPS, biases=None):
    first, second, integers = [], [], {}
    for k, (gnss, sig, freq) in enumerate(groups):
        bias = (100+k*13, 111+k*19) if biases is None else biases[k]
        for sv in range(1, 5):
            identity = raw.SignalIdentity(gnss, sv, sig, freq)
            wavelength = mg.signal_spec(identity).wavelength_m
            known = 0.02 * sv
            geometry = -unit(sv) @ BASELINE
            integer = 4*sv - 3*k
            integers[identity] = integer
            p1 = 2.1e7 + 100*sv
            l1 = p1/wavelength + 50*sv
            first.append(raw.RawxMeasurement(identity, p1, l1, -500., 2000, 45, 2, 2, 2, 7))
            second.append(raw.RawxMeasurement(identity, p1+geometry+known+bias[0],
                          l1+(geometry+known+bias[1])/wavelength+integer,
                          -501., 2100, 43, 2, 2, 2, 7))
    return (raw.RawxEpoch(100., 2408, 18, 1, 1, tuple(first)),
            raw.RawxEpoch(100., 2408, 18, 1, 1, tuple(second)), integers)


@pytest.fixture(autouse=True)
def deterministic_geometry(monkeypatch):
    def geometry(e1, e2, left, right, provider, anchor):
        assert np.array_equal(anchor, ANCHOR)
        assert left.identity == right.identity
        u = unit(left.identity.sv_id)
        known = .02 * left.identity.sv_id
        return PairGeometry(ANCHOR+2.1e7*u, ANCHOR+2.1e7*u, u, u,
                            known, 0., known, math.radians(20+left.identity.sv_id))
    monkeypatch.setattr(mg, "pair_geometry", geometry)


@pytest.mark.parametrize("gnss,sig,hz,suffix", [
    (0,0,1575.42e6,"1C"), (0,3,1227.60e6,"2L"), (0,4,1227.60e6,"2S"),
    (2,0,1575.42e6,"1C"), (2,1,1575.42e6,"1B"), (2,5,1207.14e6,"7I"),
    (2,6,1207.14e6,"7Q"), (3,0,1561.098e6,"2I"), (3,1,1561.098e6,"2I"),
    (3,2,1207.14e6,"7I"), (3,3,1207.14e6,"7I"),
])
def test_protocol_frequency_and_rinex_components(gnss, sig, hz, suffix):
    spec = mg.signal_spec(raw.SignalIdentity(gnss, 1, sig, 0))
    assert spec.frequency_hz == hz
    assert spec.rinex_suffix == suffix
    assert spec.wavelength_m * hz == pytest.approx(299792458., abs=1e-7)


@pytest.mark.parametrize("identity", [
    raw.SignalIdentity(6,1,0,7), raw.SignalIdentity(0,1,0,1),
    raw.SignalIdentity(2,1,4,0), raw.SignalIdentity(0,0,0,0),
    raw.SignalIdentity(0,33,0,0),
])
def test_fail_closed_signal_mapping(identity):
    with pytest.raises(raw.RawBackendError):
        mg.signal_spec(identity)


def test_six_groups_dimensions_sign_wavelength_and_truth():
    e1, e2, truth = fixture()
    model = mg.build_multignss_epoch(e1, e2, object(), ANCHOR, groups=GROUPS)
    assert model.y.shape == (36,)
    assert model.A.shape == (36,18)
    assert model.B.shape == (36,3)
    assert model.Q.shape == (36,36)
    assert len(model.groups) == 6
    assert len(set(model.ambiguity_labels)) == 18
    n = np.array([truth[s]-truth[g.pivot] for g in model.groups for s in g.satellites])
    np.testing.assert_allclose(model.y, model.A @ n + model.B @ BASELINE, atol=6e-9)
    assert np.linalg.matrix_rank(model.B) == 3
    assert all(mg.group_key(s) == g.key for g in model.groups for s in g.satellites)
    assert np.linalg.eigvalsh(model.Q).min() > 0


def test_shared_pivot_covariance_is_not_diagonal():
    e1, e2, _ = fixture(((0,0,0),))
    model = mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=((0,0,0),))
    np.testing.assert_allclose(model.Q[:3,:3], .5*(np.eye(3)+np.ones((3,3))))
    wave = mg.signal_spec(e1.measurements[0].identity).wavelength_m
    np.testing.assert_allclose(model.Q[3:,3:], 2*(.008*wave)**2*(np.eye(3)+np.ones((3,3))))
    np.testing.assert_array_equal(model.Q[:3,3:], np.zeros((3,3)))


def test_constellation_frequency_component_biases_cancel_only_inside_group():
    # Include both GPS L2 components; same frequency does not merge their biases.
    groups = ((0,0,0),(0,3,0),(0,4,0),(2,0,0),(3,0,0))
    e1,e2,_ = fixture(groups)
    f1,f2,_ = fixture(groups, [(400*k-91, -250*k+55) for k in range(len(groups))])
    a = mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=groups)
    b = mg.build_multignss_epoch(f1,f2,object(),ANCHOR,groups=groups)
    np.testing.assert_allclose(a.y,b.y,atol=8e-9)
    assert len(a.groups) == len(groups)


def test_full_sd_covariance_keeps_cross_frequency_and_code_phase_terms():
    groups = ((0,0,0),(0,3,0))
    e1,e2,_ = fixture(groups)
    ids = tuple(sorted(m.identity for m in e1.measurements))
    size = 2*len(ids)
    # Deterministic SPD matrix with correlated code/phase and frequency errors.
    v = np.linspace(.1,.8,size)
    qsd = np.eye(size)*.04 + np.outer(v,v)*.1
    supplied = mg.SingleDifferenceCovariance(ids,qsd)
    model = mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=groups,sd_covariance=supplied)
    d = np.zeros((6,8))
    row = 0
    for g in model.groups:
        for target in g.satellites:
            d[row,ids.index(target)] = 1
            d[row,ids.index(g.pivot)] = -1
            row += 1
    zero = np.zeros_like(d)
    transform = np.block([[d,zero],[zero,d]])
    np.testing.assert_allclose(model.Q, transform @ qsd @ transform.T, atol=1e-15)
    assert abs(model.Q[0,3]) > 1e-6
    assert abs(model.Q[0,6]) > 1e-6
    assert model.metadata["covariance_policy"] == "SUPPLIED_FULL_SD_COVARIANCE"


def test_pivot_integer_covariance_and_observation_basis_change():
    groups=((0,0,0),)
    e1,e2,truth=fixture(groups)
    ids=tuple(sorted(truth))
    a=mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=groups,pivots={groups[0]:ids[-1]})
    b=mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=groups,pivots={groups[0]:ids[0]})
    t=mg.pivot_transform(ids,ids[-1],ids[0])
    inverse=mg.pivot_transform(ids,ids[0],ids[-1])
    np.testing.assert_array_equal(t @ inverse, np.eye(3,dtype=int))
    n_a=np.array([truth[i]-truth[ids[-1]] for i in ids[:-1]])
    n_b=np.array([truth[i]-truth[ids[0]] for i in ids[1:]])
    np.testing.assert_array_equal(t @ n_a,n_b)
    z=np.zeros_like(t); full=np.block([[t,z],[z,t]])
    np.testing.assert_allclose(full @ a.y,b.y,atol=1e-13)
    np.testing.assert_allclose(full @ a.B,b.B,atol=1e-15)
    np.testing.assert_allclose(full @ a.Q @ full.T,b.Q,atol=1e-15)
    with pytest.raises(raw.RawBackendError,match="CROSS_GROUP"):
        mg.pivot_transform((*ids,raw.SignalIdentity(2,1,0,0)),ids[0],ids[1])


def test_arc_label_identity_epoch_local_and_stable_explicit():
    groups=((0,0,0),)
    e1,e2,_=fixture(groups)
    f1,f2=replace(e1,gps_tow_seconds=100.2),replace(e2,gps_tow_seconds=100.2)
    local=mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=groups)
    later=mg.build_multignss_epoch(f1,f2,object(),ANCHOR,groups=groups)
    assert set(local.ambiguity_labels).isdisjoint(later.ambiguity_labels)
    arcs={m.identity:"rx1_2/rx2_8" for m in e1.measurements}
    stable=mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=groups,arc_ids=arcs)
    next_=mg.build_multignss_epoch(f1,f2,object(),ANCHOR,groups=groups,arc_ids=arcs)
    assert stable.ambiguity_labels == next_.ambiguity_labels
    arcs[stable.groups[0].pivot] += "/reset"
    reset=mg.build_multignss_epoch(f1,f2,object(),ANCHOR,groups=groups,arc_ids=arcs)
    assert set(stable.ambiguity_labels).isdisjoint(reset.ambiguity_labels)


def test_state_failures_are_visible_and_group_failure_does_not_claim_support(monkeypatch):
    e1,e2,_=fixture(((0,0,0),(2,0,0)))
    original=mg.pair_geometry
    def missing(*args):
        if args[2].identity.gnss_id == 2:
            raise raw.RawBackendError("NO_GAL_INAV")
        return original(*args)
    monkeypatch.setattr(mg,"pair_geometry",missing)
    model=mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=((0,0,0),(2,0,0)))
    assert len(model.groups)==1
    assert len(model.metadata["rejected"])==4
    assert model.metadata["groups"][1]["status"]=="INSUFFICIENT_QUALIFIED_SATELLITES"


@pytest.mark.parametrize("change,reason", [
    ({"gps_tow_seconds":100.007},"ASYNCHRONOUS"),
    ({"receiver_status":3},"CLOCK_RESET"),
    ({"version":0},"VERSION"),
])
def test_time_reset_protocol_rejections(change,reason):
    e1,e2,_=fixture(((0,0,0),))
    with pytest.raises(raw.RawBackendError,match=reason):
        mg.build_multignss_epoch(e1,replace(e2,**change),object(),ANCHOR,groups=((0,0,0),))


def test_unavailable_fixed_pivot_and_bad_covariance():
    e1,e2,_=fixture(((0,0,0),))
    with pytest.raises(raw.RawBackendError,match="NO_QUALIFIED") as err:
        mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=((0,0,0),),
                                pivots={(0,0,0):raw.SignalIdentity(0,20,0,0)})
    assert err.value.qualification["groups"][0]["status"]=="REQUESTED_PIVOT_UNAVAILABLE"
    ids=tuple(m.identity for m in e1.measurements)
    with pytest.raises(raw.RawBackendError,match="POSITIVE_DEFINITE"):
        mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=((0,0,0),),
                                sd_covariance=mg.SingleDifferenceCovariance(ids,-np.eye(8)))


def test_checked_rtklib_adapter_uses_real_signal_code_and_no_generic_orbit():
    class Backend:
        def ephemeris_audit(self,*args):
            return raw.EphemerisAudit(100.,2408,0.,2408,0.,0,1)
        def frequency_hz(self,identity,code):
            assert code=="7I"
            return 1207.14e6
        def state(self,*args):
            return raw.SatelliteState(np.array([2.1e7,0.,0.]),np.zeros(3),0.,0.,1.,0)
    provider=CheckedRtklibProvider.__new__(CheckedRtklibProvider)
    provider.backend=Backend(); provider.last_qualification={}
    identity=raw.SignalIdentity(2,4,5,0)
    state=provider.state(identity,2408,100.,2.1e7)
    assert state.health==0
    assert provider.last_qualification[raw.identity_text(identity)]["rinex_signal"]=="7I"
    provider.backend.frequency_hz=lambda *_:1575.42e6
    with pytest.raises(raw.RawBackendError,match="FREQUENCY_MISMATCH"):
        provider.state(identity,2408,100.,2.1e7)


def test_json_group_lists_and_nonfinite_geometry_are_fail_closed(monkeypatch):
    e1,e2,_=fixture(((0,0,0),))
    assert len(mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=[[0,0,0]]).groups)==1
    original=mg.pair_geometry
    def broken(*args):
        return replace(original(*args),known_sd_m=math.nan)
    monkeypatch.setattr(mg,"pair_geometry",broken)
    with pytest.raises(raw.RawBackendError,match="NO_QUALIFIED") as exc:
        mg.build_multignss_epoch(e1,e2,object(),ANCHOR,groups=[[0,0,0]])
    assert len(exc.value.qualification["rejected"])==4
    assert all("NONFINITE" in r["reason"] for r in exc.value.qualification["rejected"])


def test_unresolved_half_cycle_and_duplicate_identity_are_not_admitted():
    e1,e2,_=fixture(((0,0,0),))
    invalid=replace(e2,measurements=tuple(replace(m,tracking_status=3) for m in e2.measurements))
    with pytest.raises(raw.RawBackendError,match="NO_QUALIFIED") as exc:
        mg.build_multignss_epoch(e1,invalid,object(),ANCHOR,groups=((0,0,0),))
    assert all("half-cycle" in r["reason"] for r in exc.value.qualification["rejected"])
    duplicate=replace(e1,measurements=e1.measurements+(e1.measurements[0],))
    with pytest.raises(raw.RawBackendError,match="DUPLICATE"):
        mg.build_multignss_epoch(duplicate,e2,object(),ANCHOR,groups=((0,0,0),))
