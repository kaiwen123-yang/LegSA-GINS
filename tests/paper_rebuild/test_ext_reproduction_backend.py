"""Independent one-way observation oracle for receiver-local DD timing."""
from dataclasses import replace
import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw
from legsa_gins.paper_rebuild.horizontal_literature import reproduction_backend as new
from legsa_gins.paper_rebuild.horizontal_literature import ext01_clambda as cl


ANCHOR = np.array([6378137., 0., 0.])
T = 100000.


class MovingSatellites:
    positions = np.array([[26000000, 0, 0], [23000000, 10000000, 6000000],
                          [22000000, -11000000, 6000000], [20000000, 4000000, -15000000],
                          [25000000, -6000000, -6000000]], float)
    velocities = np.array([[20, 2300, 800], [-1100, 1700, 700], [1400, 900, -1000],
                           [700, -2000, 500], [-500, 1300, 1700]], float)

    def at(self, sv, tx):
        i = sv-1
        # Large clock drift is intentional: an independently observable sign test.
        clock0, drift = (i+1)*1e-5, (i-2)*1e-7
        return self.positions[i]+self.velocities[i]*(tx-T), clock0+drift*(tx-T), drift

    def state(self, identity, week, tow, pseudorange_m=None):
        i = identity.sv_id-1
        b, d = (i+1)*1e-5, (i-2)*1e-7
        tx = (tow-pseudorange_m/new.C-b+d*T)/(1+d)
        p, clock, drift = self.at(identity.sv_id, tx)
        return raw.SatelliteState(p, self.velocities[i], clock, drift, 1., 0)


def independent_rotation(sat, receiver, flight):
    # Explicit matrix, independent of the production helper.
    angle = 7.2921151467e-5*flight
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c,s,0],[-s,c,0],[0,0,1.]])@sat


def epoch(provider, receiver, receiver_clock, ambiguities):
    measurements = []
    true_receive = T-receiver_clock
    for sv, ambiguity in enumerate(ambiguities, 1):
        flight = .075
        for _ in range(12):
            sat, sat_clock, _ = provider.at(sv, true_receive-flight)
            distance = np.linalg.norm(independent_rotation(sat, receiver, flight)-receiver)
            flight = distance/new.C
        code = distance+new.C*(receiver_clock-sat_clock)
        identity = raw.SignalIdentity(0, sv, 0, 0)
        phase = code/raw.wavelength_m(identity)+ambiguity
        measurements.append(raw.RawxMeasurement(identity, code, phase, 0., 6000, 45, 6, 2, 1, 7))
    return raw.RawxEpoch(T, 2400, 18, 1, 1, tuple(measurements))


def problem(baseline):
    provider = MovingSatellites()
    n1, n2 = np.array([12,-8,27,4,51]), np.array([25,9,10,-12,31])
    e1 = epoch(provider, ANCHOR, .00070, n1)
    e2 = epoch(provider, ANCHOR+baseline, .00026, n2)
    return provider, e1, e2, n2-n1


@pytest.mark.parametrize('baseline', [np.zeros(3), np.array([.15,.2,.2449489742783178])])
def test_known_baseline_and_integer_model_with_independent_receiver_clocks(baseline):
    provider, e1, e2, sd_integer = problem(baseline)
    model, audit = new.build_gps_l1_model(e1, e2, provider, ANCHOR)
    integers = np.array([sd_integer[i.sv_id-1]-sd_integer[model.pivot.sv_id-1] for i in model.satellites])
    residual = model.observation_m-model.baseline_design@baseline-model.ambiguity_design_m@integers
    assert np.max(np.abs(residual)) < 2e-5  # one-way time precision + short-baseline linearization
    assert len(audit) == 5
    assert max(abs(x['satellite_motion_sd_m']) for x in audit) > .1
    old = raw.build_gps_l1_double_difference_model(e1,e2,provider,ANCHOR)
    old_integers = np.array([sd_integer[i.sv_id-1]-sd_integer[old.pivot.sv_id-1] for i in old.satellites])
    wrong = old.observation_m-old.baseline_design@baseline-old.ambiguity_design_m@old_integers
    assert np.max(np.abs(wrong)) > .1
    # Shared pivot produces nonzero off-diagonal covariance, retained for both blocks.
    assert model.covariance_m2[0,1] > 0 and model.covariance_m2[4,5] > 0
    assert np.linalg.eigvalsh(model.covariance_m2).min() > 0


def test_time_coordinate_shift_does_not_double_correct_receiver_clock():
    provider, e1, e2, _ = problem(np.array([.1,.2,.2692582403567252]))
    before = new.pair_geometry(e1,e2,e1.measurements[2],e2.measurements[2],provider,ANCHOR)
    delta = .001
    m = e2.measurements[2]
    shifted = replace(m, pr_mes_m=m.pr_mes_m+new.C*delta,
                      cp_mes_cycles=m.cp_mes_cycles+new.C*delta/raw.wavelength_m(m.identity))
    e2new = replace(e2, gps_tow_seconds=e2.gps_tow_seconds+delta)
    after = new.pair_geometry(e1,e2new,e1.measurements[2],shifted,provider,ANCHOR)
    np.testing.assert_allclose(before.satellite2_ecef_m,after.satellite2_ecef_m,atol=1e-7,rtol=0)
    assert abs(before.known_sd_m-after.known_sd_m) < 1e-7


def test_satellite_clock_sign_and_receiver_exchange():
    provider, e1, e2, _ = problem(np.array([.1,.2,.2692582403567252]))
    g = new.pair_geometry(e1,e2,e1.measurements[0],e2.measurements[0],provider,ANCHOR)
    reverse = new.pair_geometry(e2,e1,e2.measurements[0],e1.measurements[0],provider,ANCHOR)
    assert abs(g.satellite_clock_sd_m) > .01
    assert g.known_sd_m == -reverse.known_sd_m
    np.testing.assert_array_equal(g.los2,reverse.los1)


def test_same_receiver_observation_reduces_to_zero_known_sd():
    provider,e1,_,_=problem(np.zeros(3))
    g = new.pair_geometry(e1,e1,e1.measurements[0],e1.measurements[0],provider,ANCHOR)
    assert g.known_sd_m == 0
    np.testing.assert_array_equal(g.los1,g.los2)


def test_invalid_code_cannot_be_used_for_transmit_time():
    provider,e1,e2,_=problem(np.zeros(3))
    with pytest.raises(raw.RawBackendError,match='own valid code'):
        new.pair_geometry(e1,e2,e1.measurements[0],replace(e2.measurements[0],tracking_status=6),provider,ANCHOR)


def test_noiseless_joint_float_cross_covariance_and_constrained_objective():
    b=np.array([.15,.2,.2449489742783178]); provider,e1,e2,sd=problem(b)
    model,_=new.build_gps_l1_model(e1,e2,provider,ANCHOR)
    a=np.array([sd[i.sv_id-1]-sd[model.pivot.sv_id-1] for i in model.satellites])
    floating=cl.joint_gls(model.observation_m,model.ambiguity_design_m,model.baseline_design,model.covariance_m2)
    assert np.linalg.norm(floating.covariance_ba)>0
    candidate=cl.evaluate_candidate(floating,a,.350)
    np.testing.assert_allclose(candidate.baseline,b,atol=1e-5,rtol=0)
    assert candidate.objective<1e-5
    wrong=cl.evaluate_candidate(floating,a+np.array([1,0,0,0]),.350)
    assert wrong.objective>candidate.objective+1


def dual_epochs():
    provider, e1, e2, sd = problem(np.array([.15,.2,.2449489742783178]))
    def expand(e):
        result=[]
        for gnss, sig in ((0,0),(0,3),(3,0),(3,2)):
            for m in e.measurements:
                identity=raw.SignalIdentity(gnss,m.identity.sv_id,sig,0)
                integer=round(m.cp_mes_cycles-m.pr_mes_m/raw.wavelength_m(m.identity))
                result.append(replace(m,identity=identity,cp_mes_cycles=m.pr_mes_m/raw.wavelength_m(identity)+integer))
        return replace(e,measurements=tuple(result))
    return provider,expand(e1),expand(e2),sd


def test_dual_frequency_blocks_preserve_wavelength_pivot_full_q_and_ned_sign():
    from legsa_gins.paper_rebuild.horizontal_literature.phase3_runner import _ecef_vector_to_ned
    provider,e1,e2,sd=dual_epochs()
    b=np.array([.15,.2,.2449489742783178]); bn=_ecef_vector_to_ned(b,ANCHOR)
    blocks,audit=new.build_dual_frequency_blocks(e1,e2,provider,ANCHOR,ANCHOR+b)
    assert [(x.constellation,x.frequency) for x in blocks]==[('GPS','GPS_L1'),('GPS','GPS_L2'),('BDS','BDS_B1'),('BDS','BDS_B2')]
    assert blocks[0].pivot==blocks[1].pivot and blocks[2].pivot==blocks[3].pivot
    for block in blocks:
        pivot=int(block.pivot[1:])-1
        for j,sat in enumerate(block.satellites):
            k=int(sat[1:])-1
            hb=-(np.asarray(block.los_ned[sat])-block.los_ned[block.pivot])@bn
            assert abs(block.phase_dd_m[j]-hb-block.wavelength_m*(sd[k]-sd[pivot]))<.001
        assert block.covariance_code_phase_m2[0,1]>0
        assert np.linalg.eigvalsh(block.covariance_code_phase_m2).min()>0
    assert len(audit)==20


def test_exact_signal_pairing_joint_cno_and_unmatched_component():
    provider,e1,e2,_=dual_epochs()
    first=next(m for m in e1.measurements if m.identity.gnss_id==0 and m.identity.sig_id==3)
    second=next(m for m in e2.measurements if m.identity==first.identity)
    alternate=replace(first,identity=replace(first.identity,sig_id=4),cno_dbhz=50)
    e1=replace(e1,measurements=e1.measurements+(alternate,))
    a,b,audit=new.common_signal_epochs(e1,e2)
    assert alternate.identity not in {m.identity for m in a.measurements}
    # Opposite strongest choices: joint selection uses the best minimum C/N0.
    e2=replace(e2,measurements=e2.measurements+(replace(alternate,cno_dbhz=35),))
    a,b,audit=new.common_signal_epochs(e1,e2)
    assert first.identity in {m.identity for m in a.measurements}
    assert {m.identity for m in a.measurements}=={m.identity for m in b.measurements}
    with pytest.raises(raw.RawBackendError,match='same exact SignalIdentity'):
        new.pair_geometry(e1,e2,alternate,second,provider,ANCHOR)
    with pytest.raises(raw.RawBackendError,match='exact receiver-local'):
        new.build_dual_frequency_blocks(e1,replace(e2,gps_tow_seconds=T+.001),provider,ANCHOR,ANCHOR)
