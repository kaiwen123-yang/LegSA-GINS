"""Counterexamples execute original raw_gnss functions; strict xfails are defects.

All byte frames and trajectories here are synthetic unit fixtures, never XBPG
real-data results. No historical runner or historical result is invoked.
"""
import csv
import math
import struct
import subprocess
from dataclasses import replace

import pytest

from legsa_gins.raw_gnss import doppler_velocity_ls as ls
from legsa_gins.raw_gnss import ephemeris_discovery as eph
from legsa_gins.raw_gnss import raw_doppler_clean_ablation_plot_fix as clean_plot
from legsa_gins.raw_gnss import raw_doppler_plot_data_coverage as coverage
from legsa_gins.raw_gnss import raw_doppler_plot_semantics_audit as semantics
from legsa_gins.raw_gnss import raw_doppler_spike_audit as spike
from legsa_gins.raw_gnss import raw_doppler_time_alignment as alignment
from legsa_gins.raw_gnss import raw_doppler_velocity_factor_builder as factor
from legsa_gins.raw_gnss import raw_doppler_visual_sanity as sanity
from legsa_gins.raw_gnss import rtklib_doppler_velocity_provider as provider
from legsa_gins.raw_gnss import ubx_raw_binary_rebuilder as binary
from legsa_gins.raw_gnss import ubx_rawx_parser as rawx
from legsa_gins.raw_gnss import ubx_sfrbx_scanner as sfrbx
from legsa_gins.raw_gnss.raw_doppler_types import RawDopplerMeasurement, ReceiverApproxState, SatelliteState


def frame(cls, mid, payload):
    body = bytes([cls, mid]) + struct.pack('<H', len(payload)) + payload
    return b'\xb5\x62' + body + bytes(binary.ubx_checksum(body))


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def measurement(**overrides):
    fields = dict(time=100., rcv_tow=100., week=2400, gnss_id=0, sv_id=1,
                  sig_id=0, freq_id=0, pr_mes=2.1e7, cp_mes=0., do_mes_hz=1.,
                  cno=45., do_stdev=1, trk_stat=7, wavelength_m=299792458 / 1575420000)
    return RawDopplerMeasurement(**(fields | overrides))


@pytest.mark.parametrize('gnss,sig,freq,hz', [
    (0, 3, 0, 1227600000), (0, 4, 0, 1227600000), (0, 6, 0, 1176450000),
    (2, 3, 0, 1176450000), (2, 6, 0, 1207140000),
    (3, 2, 0, 1207140000), (3, 7, 0, 1176450000),
    (5, 8, 0, 1176450000), (6, 2, 7, 1246000000),
])
@pytest.mark.xfail(strict=True, reason='RG-01: RAWX signal IDs map to wrong or missing carrier frequencies')
def test_official_signal_wavelength(gnss, sig, freq, hz):
    assert rawx.wavelength_m(gnss, sig, freq) == pytest.approx(299792458 / hz, rel=1e-13)


def test_gps_l1_wavelength_unaffected():
    assert rawx.wavelength_m(0, 0, 0) == pytest.approx(299792458 / 1575420000)


def physical_ls_fixture():
    receiver_position = (6378137., 0., 0.)
    velocity = (10., -2., 1.)
    relative_positions = [(2e7, 0., 0.), (0., 2e7, 0.), (0., 0., 2e7),
                          (14e6, 14e6, 0.), (14e6, 0., 14e6), (0., 14e6, 14e6)]
    states, measurements = {}, []
    # Differentiate physical geometric distances, not the implementation's H.
    dt = 1e-2
    for sv, relative in enumerate(relative_positions, 1):
        satellite = tuple(r + p for r, p in zip(receiver_position, relative))
        ranges = [math.dist(satellite, tuple(r + sign * dt * v for r, v in zip(receiver_position, velocity)))
                  for sign in (-1, 1)]
        range_rate = (ranges[1] - ranges[0]) / (2 * dt)
        m = measurement(sv_id=sv)
        measurements.append(replace(m, do_mes_hz=-range_rate / m.wavelength_m))
        states[sv] = SatelliteState(100., 0, sv, satellite, (0., 0., 0.))

    class Provider:
        def state_for(self, m):
            return states[m.sv_id]

    result = ls.solve_raw_doppler_velocity(measurements, Provider(), ReceiverApproxState(0., 0., receiver_position))
    return result


@pytest.mark.xfail(strict=True, reason='RG-02: receiver LOS velocity sign is inverted')
def test_ls_recovers_velocity_from_geometric_distance_derivative():
    solution = physical_ls_fixture()
    assert (solution.vn, solution.ve, solution.vd) == pytest.approx((1., -2., -10.), abs=1e-5)


def test_ls_counterexample_is_exact_opposite_not_random_numerical_noise():
    solution = physical_ls_fixture()
    assert (solution.vn, solution.ve, solution.vd) == pytest.approx((-1., 2., 10.), abs=1e-5)
    assert solution.residual_rms_mps < 1e-5


@pytest.mark.xfail(strict=True, reason='RG-03: SFRBX scanner trusts CSV label instead of UBX class/id')
def test_sfrbx_rejects_mislabeled_pvt(tmp_path):
    path = tmp_path / 'raw.csv'
    write_csv(path, [{'name': 'UBX-RXM-SFRBX', 'data': repr(frame(1, 7, bytes(92)))}])
    assert sfrbx.scan_sfrbx_csv(path)['message_count'] == 0


@pytest.mark.xfail(strict=True, reason='RG-03: RAWX declared numMeas=2 with one record is silently partially accepted')
def test_rawx_payload_count_is_exact():
    head = struct.pack('<dHbbBBH', 100., 2400, 18, 2, 1, 1, 0)
    record = struct.pack('<ddfBBBBHBBBBBB', 2.1e7, 1e5, 25., 0, 3, 0, 0, 10, 45, 1, 1, 1, 7, 0)
    assert rawx.parse_rawx_frame(frame(2, 0x15, head + record)) == []


@pytest.mark.xfail(strict=True, reason='RG-03: grouping ignores GPS week and receiver identity')
def test_epoch_group_does_not_merge_different_weeks_or_receivers():
    a = measurement(source_file='gnss1')
    b = replace(a, week=a.week + 1)
    c = replace(a, source_file='gnss2')
    assert len(rawx.group_epochs([a, b, c])) == 3


@pytest.mark.xfail(strict=True, reason='RG-04: invalid frame inside mixed valid+bad cell disappears from invalid counter')
def test_rebuilder_counts_bad_frame_in_mixed_cell(tmp_path):
    good = frame(1, 7, bytes(92))
    bad = good[:-1] + bytes([good[-1] ^ 1])
    source = tmp_path / 'raw.csv'
    write_csv(source, [{'data': repr(good + bad)}])
    result = binary.rebuild_csv_to_ubx(source, tmp_path / 'raw.ubx')
    assert result['frame_count'] == 1
    assert result['invalid_frame_count'] == 1


def test_rebuilder_preserves_hpposecef_signed_high_precision_bytes(tmp_path):
    payload = bytearray(28)
    struct.pack_into('<Iiii', payload, 4, 1000, -100, 200, -300)
    struct.pack_into('<bbbBI', payload, 20, -12, 34, -56, 0, 123)
    original = frame(1, 0x13, bytes(payload))
    source, output = tmp_path / 'raw.csv', tmp_path / 'raw.ubx'
    write_csv(source, [{'data': repr(original)}])
    result = binary.rebuild_csv_to_ubx(source, output)
    assert result['frame_count'] == 1
    assert output.read_bytes() == original


def provider_row(time):
    return dict(time=str(time), source_epoch_time=str(time), vn='1', ve='2', vd='3',
                std_vn='.2', std_ve='.2', std_vd='.2', sat_count='8', provider_status='available')


@pytest.mark.xfail(strict=True, reason='RG-07: factor builder infers time offset only from first epochs')
def test_unrelated_times_cannot_be_automatically_aligned(tmp_path):
    path = tmp_path / 'provider.csv'
    write_csv(path, [provider_row(1000), provider_row(1001)])
    clean = tmp_path / 'clean.gnss'
    clean.write_text('10 30 120 1\n11 30 120 1\n', encoding='utf-8')
    result = factor.build_factor_file_from_provider(path, tmp_path / 'out', clean_gnss_path=clean)
    assert not result['raw_doppler_solver_activation_allowed']


@pytest.mark.xfail(strict=True, reason='RG-08: zero actual updates accepted as alignment OK')
def test_no_actual_updates_is_not_successful_update_alignment(tmp_path):
    path = tmp_path / 'factor.csv'
    write_csv(path, [{'time': '1'}, {'time': '2'}])
    result = alignment.analyze_factor_time_alignment(path, [1., 2.], [1., 2.], {'raw_doppler_update_count': 0})
    assert result['update_alignment_ok'] is False


@pytest.mark.xfail(strict=True, reason='RG-08: same factor is counted as multiple expected updates')
def test_factor_consumption_is_unique(tmp_path):
    path = tmp_path / 'factor.csv'
    write_csv(path, [{'time': '1.01'}])
    result = alignment.analyze_factor_time_alignment(path, [1., 1.02], [1., 1.02], {'raw_doppler_update_count': 2})
    assert result['expected_update_count'] <= result['factor_epoch_count']


@pytest.mark.xfail(strict=True, reason='RG-09: extension-only score is treated as BY2 date match')
def test_unrelated_nav_file_is_not_verified_date_match(tmp_path):
    (tmp_path / 'other_day.nav').write_text('unparsed fixture', encoding='utf-8')
    assert eph.discover_ephemeris([tmp_path])['by2_date_match'] is False


@pytest.mark.xfail(strict=True, reason='RG-10: old repaired difference plot subtracts row indices rather than common times')
def test_plot_difference_uses_common_time_support(tmp_path):
    baseline = [{'timestamp': 0., 'e': 10.}, {'timestamp': 1., 'e': 20.}, {'timestamp': 2., 'e': 30.}]
    raw = [{'timestamp': 0., 'e': 1.}, {'timestamp': 2., 'e': 3.}]
    source = clean_plot._diff_source(tmp_path / 'unused.png', baseline, raw, 'e')
    assert source['series'][0]['x'] == [0., 2.]
    assert source['series'][0]['y'] == [9., 27.]


@pytest.mark.xfail(strict=True, reason='RG-10: missing metric is converted to zero improvement')
def test_missing_plot_metric_stays_missing():
    assert math.isnan(semantics._metric_delta({}, 'yaw_rmse_deg'))


@pytest.mark.xfail(strict=True, reason='RG-11: vacuous all() accepts no mandatory figures')
def test_empty_figure_coverage_does_not_pass():
    assert coverage.validate_required_figure_coverage([])['mandatory_coverage_passed'] is False


@pytest.mark.xfail(strict=True, reason='RG-11: zero update variants are excluded from consistency check')
def test_enabled_variant_with_zero_update_fails_consistency():
    variants = [dict(enable_raw_doppler=True, raw_doppler_update_count=n) for n in (3, 0)]
    assert sanity._variant_update_counts_ok(variants)[0] is False


@pytest.mark.xfail(strict=True, reason='RG-12: a global update count does not identify whether a spike epoch was applied')
def test_spike_application_requires_per_epoch_evidence(tmp_path):
    path = tmp_path / 'factors.csv'
    first, second = provider_row(0), provider_row(1)
    second['vn'] = '10'
    write_csv(path, [first, second])
    result = spike.audit_raw_doppler_spikes(factor_csv=path,
        update_manifest={'raw_doppler_update_count': 1, 'raw_doppler_reject_count': 1})
    assert result['spike_epochs'][0]['raw_doppler_update_applied'] == 'evidence_missing'


def prepared_helper_csv(tmp_path, monkeypatch, returncode):
    for name in ('helper', 'obs', 'nav'):
        (tmp_path / name).write_text('fixture', encoding='utf-8')
    write_csv(tmp_path / 'RTKLIB_HELPER_DOPPLER_ECEF_VELOCITY.csv',
              [dict(time=1., source_epoch_time=1., vecef_x=1., vecef_y=2., vecef_z=3.,
                    std_vx=1., std_vy=2., std_vz=3., sat_count=8, doppler_obs_count=8,
                    provider_status='available', quality_flag=5)])
    monkeypatch.setattr(provider, '_run_helper', lambda *args:
        (subprocess.CompletedProcess(['fixture'], returncode, '', 'fixture'), ['fixture'], 'mock_boundary'))
    return provider.run_rtklib_doppler_velocity_provider(obs_path=tmp_path / 'obs',
        nav_path=tmp_path / 'nav', helper_exe=tmp_path / 'helper', output_dir=tmp_path,
        approx_position_source={'lat_deg': 0., 'lon_deg': 0., 'height_m': 0.})


@pytest.mark.xfail(strict=True, reason='RG-13: stale helper CSV wins over failed subprocess return status')
def test_failed_helper_does_not_activate_stale_velocity(tmp_path, monkeypatch):
    report = prepared_helper_csv(tmp_path, monkeypatch, returncode=3)
    assert report['helper_returncode'] == 3
    assert report['solver_activation_allowed'] is False


@pytest.mark.xfail(strict=True, reason='RG-06: ECEF per-axis sigmas are renamed rather than rotated to NED')
def test_provider_rotates_anisotropic_ecef_covariance(tmp_path, monkeypatch):
    report = prepared_helper_csv(tmp_path, monkeypatch, returncode=0)
    with open(report['factor_csv_path'], newline='', encoding='utf-8') as stream:
        row = next(csv.DictReader(stream))
    # At lat=lon=0, N=Z, E=Y, D=-X: diagonal sigma [1,2,3] must become [3,2,1].
    assert [float(row[k]) for k in ('std_vn', 'std_ve', 'std_vd')] == [3., 2., 1.]
