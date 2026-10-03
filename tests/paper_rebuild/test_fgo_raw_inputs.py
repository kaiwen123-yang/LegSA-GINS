"""Scientific signs/units for the new undifferenced input adapter."""
import numpy as np
import pytest
from legsa_gins.paper_rebuild.fgo_comparison.raw_inputs import (
    C, OMEGA, code_sigma, doppler_wls, solve_code_wls,
    bootstrap_code, apply_broadcast_gate, raw,
)
from legsa_gins.paper_rebuild.fgo_comparison.broadcast_identity import BroadcastClockGate


def geometry():
    p=np.array([-2178000.,4387000.,4078000.])
    directions=np.array([[1,1,1],[1,-1,1],[-1,1,1],[-1,-1,1],[1,0,-1],[0,1,-1],[0,-1,-1],[1,2,3]],float)
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    return p,p+directions*2.1e7


def test_code_wls_recovers_two_independent_clocks_without_prior():
    p,sat=geometry();system=np.array([0,0,0,0,1,1,1,1])
    clock=np.array([599584.916,599620.123])
    code=np.linalg.norm(sat-p,axis=1)+clock[system]
    out=solve_code_wls(sat,code,np.linspace(1,3,8),system,p+[100,-300,200])
    np.testing.assert_allclose(out[0],p,atol=2e-8,rtol=0)
    np.testing.assert_allclose(out[1],clock,atol=2e-8,rtol=0)


def test_rawx_doppler_negative_range_rate_with_satellite_clock_and_earth_rate():
    p,sat=geometry();v=np.array([1.2,-.4,.05]);drift=7.2
    sv=np.arange(24,dtype=float).reshape(8,3)*100-1100
    dts=np.linspace(-1e-10,2e-10,8);freq=np.full(8,1575.42e6)
    u=(sat-p)/np.linalg.norm(sat-p,axis=1)[:,None]
    rate=np.sum(u*(sv-v),axis=1)+OMEGA/C*(sv[:,1]*p[0]+sat[:,1]*v[0]-sat[:,0]*v[1]-sv[:,0]*p[1])+drift-C*dts
    raw_d=-rate*freq/C
    out=doppler_wls(sat,sv,dts,freq,raw_d,np.full(8,.1),p)
    np.testing.assert_allclose(out[0],v,atol=1e-9,rtol=0)
    np.testing.assert_allclose(out[2],drift,atol=1e-9,rtol=0)
    assert np.linalg.eigvalsh(out[1]).min()>0


def test_code_cofactor_has_correct_noise_direction_and_clock_rank_failure():
    pars={'T':45,'A':30,'a':30,'F':10}
    assert code_sigma(np.deg2rad(10),30,pars)>code_sigma(np.deg2rad(80),30,pars)
    assert code_sigma(np.deg2rad(45),20,pars)>code_sigma(np.deg2rad(45),45,pars)
    p,sat=geometry()
    assert solve_code_wls(sat[:3],np.full(3,2e7),np.ones(3),np.zeros(3,int),p) is None


def test_bootstrap_expected_missing_observations_are_distinct_from_abi_error():
    class Stub:
        def __init__(self, message): self.message=message
        def pntpos_rawx_epoch(self,*args): raise raw.PntPosBridgeError(self.message,-1)
    assert bootstrap_code(Stub('PNTPOS_NO_SUPPORTED_RAW_MEASUREMENTS'),None,{}) is None
    with pytest.raises(raw.PntPosBridgeError): bootstrap_code(Stub('ABI_MISMATCH'),None,{})


def _navigation(path, records):
    """Synthetic RINEX-3 messages; no actual navigation file is opened."""
    text = '     3.04           N: GNSS NAV DATA    M: Mixed            RINEX VERSION / TYPE\n'
    text += '                                                            END OF HEADER\n'
    for spec in records:
        satellite = spec.get('satellite', 'C13')
        data = np.zeros(31)
        data[:3] = spec.get('clock', [-.00035, -1.7e-11, 0.])
        data[3] = spec.get('iode', 6)
        data[4:11] = [187., 4.9e-10, 1.6, 6.5e-6, .0058, 1.7e-5, 6493.]
        data[11] = spec.get('toe', 457200.)
        data[12:20] = [-6.e-8, -2.09, -6.3e-8, 1.04, -279.7, -2.22, -1.7e-9, 9.3e-10]
        data[21] = 1052 if satellite[0] == 'C' else 2408
        data[23] = 2.
        data[25:27] = [-1.e-8, 2.e-9]
        data[28 if satellite[0] == 'C' else 26] = spec.get('iodc', 0)
        data[27] = spec.get('transmission', 460500.)
        prefix = f"{satellite} 2026 03 06 {spec.get('hour', 7):02d} 00 00"
        text += prefix + ''.join(f'{value:19.12E}' for value in data[:3]) + '\n'
        for i in range(3, 31, 4):
            text += '    ' + ''.join(f'{value:19.12E}' for value in data[i:i + 4]) + '\n'
    path.write_text(text, encoding='ascii')
    return path


class _SelectedEphemeris:
    """Synthetic metadata-only bridge; never computes a satellite state."""
    def __init__(self, record):
        self.record, self.calls = record, 0

    def ephemeris_audit(self, identity, week, tow):
        self.calls += 1
        if self.record is None:
            raise raw.RawBackendError('synthetic missing selected navigation')
        toe_week, toe_tow = divmod(self.record.toe_gpst_s, 604800.)
        toc_week, toc_tow = divmod(self.record.toc_gpst_s, 604800.)
        return raw.EphemerisAudit(week * 604800. + tow - self.record.toe_gpst_s,
            int(toe_week), toe_tow, int(toc_week), toc_tow, 0, self.record.iode)


def test_broadcast_identical_duplicate_and_public_quantization_are_not_conflicts(tmp_path):
    one = _navigation(tmp_path/'one.nav', [{}])
    two = _navigation(tmp_path/'two.nav', [dict(transmission=460710),
        dict(clock=[-.00035 + 2.**-35, -1.7e-11, 0.], transmission=460740)])
    gate = BroadcastClockGate.from_paths([one, two])
    assert gate.report['source_navigation_record_count'] == 3
    assert gate.report['physical_key_count'] == 1
    assert gate.report['conflicting_physical_key_count'] == 0
    assert gate.decision('C13', 2408, 460700.) is None


def test_broadcast_conflict_is_order_independent_without_source_or_timestamp_vote(tmp_path):
    one = _navigation(tmp_path/'one.nav', [dict(clock=[-.00012, -1.7e-11, 3.2e-18], transmission=460710)])
    two = _navigation(tmp_path/'two.nav', [{}, dict(transmission=460740)])
    first = BroadcastClockGate.from_paths([one, two])
    reverse = BroadcastClockGate.from_paths([two, one])
    assert first.report == reverse.report
    conflict = first.report['conflicts'][0]
    assert conflict['conflicting_clock_fields'] == ['af0', 'af2']
    assert len(conflict['records']) == 3  # repeated agreeing pages do not vote away the conflict
    decision = first.decision('C13', 2408, 460700.)
    assert decision['reason'] == 'BROADCAST_CLOCK_CONFLICT'
    assert decision['conflicting_physical_keys'] == [conflict['physical_key_sha256']]
    assert first.report['navigation_records_removed'] == 0
    assert not first.report['fallback_after_conflict']


def test_broadcast_legitimate_toc_aodc_and_gps_iodc_changes_are_distinct_versions(tmp_path):
    path = _navigation(tmp_path/'versions.nav', [{},
        dict(clock=[-.00012, -1.7e-11, 0.], hour=8),
        dict(clock=[-.00011, -1.7e-11, 0.], iodc=1),
        dict(satellite='G07'), dict(satellite='G07', iodc=1, clock=[-.00013, -1.7e-11, 0.])])
    gate = BroadcastClockGate.from_paths([path])
    assert gate.report['physical_key_count'] == 5
    assert gate.report['conflicting_physical_key_count'] == 0
    assert gate.decision('C13', 2408, 460700.) is None
    assert gate.decision('G07', 2408, 460700.) is None


def test_broadcast_conflict_cannot_fall_back_but_closer_legal_identity_remains_usable(tmp_path):
    path = _navigation(tmp_path/'identities.nav', [dict(toe=456000., iode=5), {},
        dict(clock=[-.00012, -1.7e-11, 0.], transmission=460710),
        # A distinct but equal-Toe clock version cannot resolve the ambiguity.
        dict(hour=8, iodc=1), dict(toe=465000., iode=7, hour=9)])
    gate = BroadcastClockGate.from_paths([path])
    assert gate.decision('C13', 2408, 457500.)['reason'] == 'BROADCAST_CLOCK_CONFLICT'
    assert gate.decision('C13', 2408, 465100.) is None
    assert gate.decision('C13', 2408, 500000.)['reason'] == 'NO_APPLICABLE_BROADCAST_NAVIGATION'
    assert gate.decision('G07', 2408, 460700.)['reason'] == 'NO_APPLICABLE_BROADCAST_NAVIGATION'
    measurement = raw.RawxMeasurement(raw.SignalIdentity(3, 13, 0, 0),
        2.1e7, 1.e8, -1500., 1000, 45, 1, 1, 1, 3)
    epoch = raw.RawxEpoch(465100., 2408, 18, 0, 1, (measurement,))
    # The nearer legal record really survives and is selected by the bridge.
    coarse, permitted, counts = apply_broadcast_gate(epoch, [measurement], gate, _SelectedEphemeris(gate.records[-1]))
    assert coarse is epoch and permitted == [measurement]
    assert counts['post_uniqnav_selection_audits'][0]['post_uniqnav_decision'] is None


def test_broadcast_actual_post_uniqnav_selection_blocks_discarded_nearer_key(tmp_path):
    # RTKLIB uniqeph sorts ttr then toe then sat, and adjacent same sat/IODE
    # records are discarded. All three have IODE 6: only the first old Toe
    # survives, although the original navigation has a strictly closer key.
    path = _navigation(tmp_path/'uniq.nav', [dict(toe=450000., transmission=100.),
        dict(toe=450000., transmission=101., clock=[-.00012, -1.7e-11, 0.]),
        dict(toe=460000., transmission=102.)])
    gate = BroadcastClockGate.from_paths([path])
    assert gate.decision('C13', 2408, 460100.) is None
    measurement = raw.RawxMeasurement(raw.SignalIdentity(3, 13, 0, 0),
        2.1e7, 1.e8, -1500., 1000, 45, 1, 1, 1, 3)
    epoch = raw.RawxEpoch(460100., 2408, 18, 0, 1, (measurement,))
    with pytest.raises(ValueError, match='BROADCAST_SELECTION_AUDIT_PROVIDER_REQUIRED'):
        apply_broadcast_gate(epoch, [measurement], gate)
    provider = _SelectedEphemeris(gate.records[0])
    coarse, permitted, counts = apply_broadcast_gate(epoch, [measurement], gate, provider)
    assert provider.calls == 1 and coarse.measurements == () and permitted == []
    assert counts['raw_signal_denominator'] == counts['selected_code_denominator'] == 1
    assert counts['excluded_selected_codes'] == {'BROADCAST_CLOCK_CONFLICT': 1}
    assert counts['unavailable_satellites'][0]['dependency_stage'] == 'POST_UNIQNAV_SELECTED_EPHEMERIS'
    # No actual retained navigation is also an explicit unavailable epoch,
    # never permission to run with the original unverified observations.
    coarse, permitted, counts = apply_broadcast_gate(epoch, [measurement], gate, _SelectedEphemeris(None))
    assert coarse.measurements == () and permitted == []
    assert counts['excluded_selected_codes'] == {'NO_POST_UNIQNAV_BROADCAST_NAVIGATION': 1}


def test_broadcast_gate_preserves_raw_epoch_denominators_and_screens_bootstrap(tmp_path):
    path = _navigation(tmp_path/'nav.nav', [{}, dict(clock=[-.00012, -1.7e-11, 0.]), dict(satellite='G07')])
    gate = BroadcastClockGate.from_paths([path])
    def measurement(gnss, satellite):
        return raw.RawxMeasurement(raw.SignalIdentity(gnss, satellite, 0, 0),
            2.1e7, 1.e8, -1500., 1000, 45, 1, 1, 1, 3)
    bad, good = measurement(3, 13), measurement(0, 7)
    epoch = raw.RawxEpoch(460700., 2408, 18, 0, 1, (bad, good))
    provider = _SelectedEphemeris(gate.records[0])
    coarse, permitted, counts = apply_broadcast_gate(epoch, [bad, good], gate, provider)
    assert epoch.measurements == (bad, good)  # immutable raw observations unchanged
    assert coarse.measurements == (good,) and permitted == [good]
    assert (coarse.gps_week, coarse.gps_tow_seconds) == (epoch.gps_week, epoch.gps_tow_seconds)
    assert counts['raw_signal_denominator'] == counts['selected_code_denominator'] == 2
    assert counts['permitted_selected_codes'] == 1
    assert counts['excluded_selected_codes'] == {'BROADCAST_CLOCK_CONFLICT': 1}
    assert counts['code_and_associated_doppler_excluded_together']
    # An entirely unavailable epoch still exists, including its denominator.
    unavailable = raw.RawxEpoch(460701., 2408, 18, 0, 1, (bad,))
    coarse, permitted, counts = apply_broadcast_gate(unavailable, [bad], gate, provider)
    assert coarse.gps_tow_seconds == 460701. and coarse.measurements == ()
    assert permitted == [] and counts['selected_code_denominator'] == 1
    # An unambiguous epoch reaches the old coarse-SPP API unchanged.
    clean = raw.RawxEpoch(460702., 2408, 18, 0, 1, (good,))
    coarse, permitted, counts = apply_broadcast_gate(clean, [good], gate, provider)
    assert coarse is clean and permitted == [good]
    assert provider.calls == 2  # no metadata ABI query for the unambiguous GPS satellite
