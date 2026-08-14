import csv
import ctypes
import struct

import numpy as np
import pytest

import legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend as backend

from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import (
    RawBackendError,
    RawxEpoch,
    RawxMeasurement,
    RtklibBroadcastProvider,
    SatelliteState,
    SignalIdentity,
    TrackingContinuity,
    build_gps_l1_double_difference_model,
    correlated_dd_covariance,
    decode_nav_sat,
    decode_rawx,
    decode_sfrbx,
    gps_l1_code_spp,
    iter_ubx_frames,
    line_of_sight,
    pair_epochs,
    parse_csv_data_cell,
    rawx_standard_deviations,
    reconstruct_ubx_stream,
    select_reference,
    signal_frequency_hz,
    strict_raw_tracking_eligible,
    single_and_double_differences,
    ubx_checksum,
)


def _measurement(sv=3, lock=1000, trk=0x07, freq=0, cp_std=2):
    return RawxMeasurement(SignalIdentity(0, sv, 0, freq), 20e6, 100.0, -2.0,
                           lock, 40, 1, cp_std, 3, trk)


def _epoch(tow, measurements=(), week=2400, status=1):
    return RawxEpoch(tow, week, 18, status, 1, tuple(measurements))


def _ubx_frame(message_class, message_id, payload):
    body = bytes((message_class, message_id)) + struct.pack("<H", len(payload)) + payload
    return b"\xb5\x62" + body + bytes(ubx_checksum(body))


def test_csv_ubx_rawx_and_sfrbx_boundaries_and_checksum():
    assert parse_csv_data_cell("0x01, 2, 255") == b"\x01\x02\xff"
    assert parse_csv_data_cell("0102ff") == b"\x01\x02\xff"
    record = struct.pack("<ddfBBBBHBBBBBB", 20e6, 12.5, -3.0, 0, 7, 0, 0,
                         1234, 45, 1, 2, 3, 0x03, 0)
    rawx = struct.pack("<dHbBBB2s", 100.25, 2400, 18, 1, 1, 1, b"\0\0") + record
    body = bytes((0x02, 0x15)) + struct.pack("<H", len(rawx)) + rawx
    frame = b"\xb5\x62" + body + bytes(ubx_checksum(body))
    message = list(iter_ubx_frames(frame))
    assert message[0][:2] == (0x02, 0x15)
    epoch = decode_rawx(message[0][2])
    assert (epoch.gps_week, epoch.gps_tow_seconds, epoch.leap_seconds) == (2400, 100.25, 18)
    assert epoch.measurements[0].identity == SignalIdentity(0, 7, 0, 0)
    assert epoch.measurements[0].carrier_valid
    sfrbx = struct.pack("<BBBBBBBBII", 1, 123, 1, 0, 2, 4, 2, 32,
                        0x1234, 0x5678)
    decoded_sfrbx = decode_sfrbx(sfrbx)
    assert decoded_sfrbx.words == (0x1234, 0x5678)
    assert (decoded_sfrbx.gnss_id, decoded_sfrbx.sv_id, decoded_sfrbx.reserved1,
            decoded_sfrbx.freq_id, decoded_sfrbx.channel,
            decoded_sfrbx.reserved2) == (1, 123, 1, 0, 4, 32)
    malformed_sfrbx = struct.pack("<BBBBBBBBI", 0, 7, 1, 0, 1, 0, 3, 17, 0x1234)
    with pytest.raises(RawBackendError, match="SFRBX"):
        decode_sfrbx(malformed_sfrbx)
    with pytest.raises(RawBackendError, match="checksum"):
        list(iter_ubx_frames(frame[:-1] + b"\0"))
    with pytest.raises(RawBackendError, match="truncated"):
        list(iter_ubx_frames(frame[:-3]))


def test_pairing_reference_switch_cycle_slip_and_correlated_dd():
    left = [_epoch(1.0), _epoch(2.0)]
    right = [_epoch(1.0), _epoch(3.0)]
    pairs, failures = pair_epochs(left, right)
    assert len(pairs) == 1 and len(failures) == 2
    assert len(pairs) + sum(x["receiver"] == 1 for x in failures) == len(left)
    mismatch_pairs, _ = pair_epochs([_epoch(1.0)], [_epoch(1.0 + 5e-7)])
    assert mismatch_pairs == []
    with pytest.raises(RawBackendError, match="frozen"):
        pair_epochs([_epoch(1.0)], [_epoch(1.0)], 1e-6)
    duplicate_pairs, duplicate_failures = pair_epochs([_epoch(4.0)], [_epoch(4.0), _epoch(4.0)])
    assert duplicate_pairs == []
    assert all(item["code"] == "PAIR_AMBIGUOUS" for item in duplicate_failures)
    assert sum(item["receiver"] == 1 for item in duplicate_failures) == 1
    assert sum(item["receiver"] == 2 for item in duplicate_failures) == 2

    low = _measurement(3, lock=500)
    high = _measurement(8, lock=400)
    elevations = {low.identity: 0.4, high.identity: 0.8}
    first, switched = select_reference([low, high], elevations)
    assert (first, switched) == (high.identity, False)
    second, switched = select_reference([low], elevations, first)
    assert second == low.identity and switched

    continuity = TrackingContinuity()
    assert continuity.update(1, _epoch(1.0), _measurement(lock=1000)).arc_reset
    flags = continuity.update(1, _epoch(2.0), _measurement(lock=10))
    assert flags.lock_reset and flags.cycle_slip and flags.arc_reset
    half = continuity.update(1, _epoch(3.0), _measurement(lock=20, trk=0x0F))
    assert half.half_cycle_valid and half.half_cycle_subtracted and half.cycle_slip
    repeated_half = continuity.update(1, _epoch(3.5), _measurement(lock=25, trk=0x0F))
    assert repeated_half.half_cycle_subtracted and not repeated_half.cycle_slip
    assert strict_raw_tracking_eligible(repeated_half_measurement := _measurement(lock=25, trk=0x0F))
    assert repeated_half_measurement.half_cycle_subtracted
    invalid = continuity.update(1, _epoch(4.0), _measurement(lock=30, trk=0x01))
    assert invalid.pseudorange_valid and not invalid.carrier_valid and invalid.arc_reset
    restored = continuity.update(1, _epoch(5.0), _measurement(lock=40, trk=0x07))
    assert restored.carrier_valid and restored.arc_reset
    clock = continuity.update(1, _epoch(6.0, status=0x02), _measurement(lock=50))
    assert clock.receiver_clock_reset and clock.arc_reset

    rollover = TrackingContinuity()
    rollover.update(1, _epoch(604799.0, week=2400), _measurement(lock=10))
    forward = rollover.update(1, _epoch(0.0, week=2401), _measurement(lock=20))
    assert not forward.cycle_slip

    with pytest.raises(RawBackendError, match="reference"):
        select_reference([_measurement(trk=0x03)], {_measurement(trk=0x03).identity: 0.5})

    covariance = correlated_dd_covariance([2.0, 3.0], 0.5)
    np.testing.assert_allclose(covariance, [[2.5, 0.5], [0.5, 3.5]])
    r1 = {low.identity: 10.0, high.identity: 20.0}
    r2 = {low.identity: 11.0, high.identity: 23.0}
    assert single_and_double_differences(r1, r2, low.identity)[high.identity] == 2.0


def test_signal_registry_stochastic_floors_and_synthetic_state_geometry():
    assert signal_frequency_hz(SignalIdentity(6, 1, 0, 0)) == pytest.approx(1598.0625e6)
    assert signal_frequency_hz(SignalIdentity(2, 1, 5, 0)) == pytest.approx(1207.14e6)
    with pytest.raises(RawBackendError, match="FDMA"):
        signal_frequency_hz(SignalIdentity(6, 1, 0, 14))
    with pytest.raises(RawBackendError, match="freqId"):
        signal_frequency_hz(SignalIdentity(0, 1, 0, 1))
    assert rawx_standard_deviations(_measurement()) == pytest.approx((0.50, 0.008, 0.02))
    with pytest.raises(RawBackendError, match="cpStdev"):
        rawx_standard_deviations(_measurement(cp_std=15))

    class TrustedSyntheticProvider:
        status = "SYNTHETIC_TEST_ONLY"

        def state(self, identity, gps_week, gps_tow_seconds):
            return SatelliteState(np.array([20_000_000.0, 0.0, 0.0]), np.zeros(3))

    state = TrustedSyntheticProvider().state(SignalIdentity(0, 3, 0, 0), 2400, 1.0)
    np.testing.assert_allclose(line_of_sight([0, 0, 0], state.position_ecef_m), [1, 0, 0])


def test_reconstruct_scans_python_bytes_and_audits_rawx_sfrbx_nav_sat(tmp_path):
    record = struct.pack("<ddfBBBBHBBBBBB", 22e6, 12.5, -3.0, 0, 7, 0, 0,
                         1234, 45, 1, 2, 3, 0x0F, 0)
    rawx_payload = struct.pack("<dHbBBB2s", 100.25, 2400, 18, 1, 1, 1, b"\x12\x34") + record
    sfrbx_payload = struct.pack("<BBBBBBBBII", 0, 7, 0, 0, 2, 0, 2, 0,
                                0x1234, 0x5678)
    nav_sat_payload = struct.pack("<IBBHBBBbhhI", 100250, 1, 1, 0, 0, 7, 44,
                                  31, 123, -4, 0x08)
    rawx_frame = _ubx_frame(0x02, 0x15, rawx_payload)
    sfrbx_frame = _ubx_frame(0x02, 0x13, sfrbx_payload)
    nav_sat_frame = _ubx_frame(0x01, 0x35, nav_sat_payload)
    damaged = bytearray(sfrbx_frame)
    damaged[-1] ^= 1
    source = tmp_path / "raw.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["data"])
        writer.writeheader()
        writer.writerow({"data": repr(b"noise" + rawx_frame + bytes(damaged) + nav_sat_frame)})
        writer.writerow({"data": repr(sfrbx_frame)})
    output = tmp_path / "reconstructed.ubx"
    audit = reconstruct_ubx_stream(source, output)
    assert output.read_bytes() == rawx_frame + nav_sat_frame + sfrbx_frame
    assert audit.message_counts == {"01-35": 1, "02-13": 1, "02-15": 1}
    assert len(audit.rawx_epochs) == len(audit.sfrbx_messages) == len(audit.nav_sat_epochs) == 1
    assert audit.checksum_failure_count == 1
    assert audit.discarded_byte_count > 0
    assert decode_nav_sat(nav_sat_payload).satellites[0].elevation_deg == 31


class _GeometryProvider:
    status = "SYNTHETIC_TEST_ONLY"

    def __init__(self, positions):
        self.positions = positions

    def state(self, identity, gps_week, gps_tow_seconds, pseudorange_m=None):
        return SatelliteState(np.asarray(self.positions[identity], dtype=float), np.zeros(3),
                              health=0)


def test_gps_code_spp_and_real_dd_matrix_are_finite():
    receiver1 = np.array([6_378_147.0, 100.0, 50.0])
    receiver2 = receiver1 + np.array([0.0, 0.35, 0.0])
    directions = (
        np.array([0.80, 0.50, 0.33]), np.array([0.75, -0.55, 0.36]),
        np.array([0.70, 0.20, -0.68]), np.array([0.65, -0.15, -0.75]),
        np.array([0.90, 0.05, 0.43]), np.array([0.60, 0.75, -0.28]),
    )
    identities = tuple(SignalIdentity(0, index + 1, 0, 0) for index in range(len(directions)))
    positions = {
        identity: receiver1 + 22_000_000.0 * direction / np.linalg.norm(direction)
        for identity, direction in zip(identities, directions)
    }
    provider = _GeometryProvider(positions)

    def make_epoch(receiver, receiver_index):
        measurements = []
        for index, identity in enumerate(identities):
            initial_range = np.linalg.norm(positions[identity] - receiver)
            corrected = backend.earth_rotation_correct_satellite(
                positions[identity], initial_range / 299_792_458.0
            )
            pseudorange = float(np.linalg.norm(corrected - receiver))
            cycles = pseudorange / backend.wavelength_m(identity) + receiver_index * (index + 2)
            measurements.append(RawxMeasurement(identity, pseudorange, cycles, -2.0,
                                                2000, 45, 1, 2, 3, 0x0F))
        return _epoch(100.0, measurements)

    first, second = make_epoch(receiver1, 0), make_epoch(receiver2, 1)
    spp = gps_l1_code_spp(first, provider)
    np.testing.assert_allclose(spp.position_ecef_m, receiver1, atol=0.1)
    assert spp.satellite_count == 6 and np.isfinite(spp.residual_rms_m)
    model = build_gps_l1_double_difference_model(
        first, second, provider, receiver1, minimum_elevation_rad=-np.pi / 2
    )
    assert model.observation_m.shape == (10,)
    assert model.ambiguity_design_m.shape == (10, 5)
    assert model.baseline_design.shape == (10, 3)
    assert model.covariance_m2.shape == (10, 10)
    assert np.all(np.isfinite(model.covariance_m2))
    assert np.all(np.linalg.eigvalsh(model.covariance_m2) > 0)


def test_rtklib_ctypes_adapter_loads_multiple_nav_and_transmit_state(tmp_path, monkeypatch):
    class FakeFunction:
        def __init__(self, implementation):
            self.implementation = implementation
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.implementation(*args)

    class FakeLibrary:
        def __init__(self):
            self.freed = False
            self.legsa_nav_load_rinex_paths = FakeFunction(lambda paths, count: 1234 if count == 2 else 0)
            self.legsa_nav_free = FakeFunction(self._free)
            self.legsa_nav_counts = FakeFunction(self._counts)
            self.legsa_sat_id_to_no = FakeFunction(lambda satellite: 7 if satellite == b"G07" else 0)
            self.legsa_satpos_broadcast = FakeFunction(self._state)
            self.legsa_satpos_transmit_broadcast = FakeFunction(self._transmit_state)
            self.legsa_broadcast_ephemeris_audit = FakeFunction(self._ephemeris_audit)
            self.legsa_sat_frequency_hz = FakeFunction(lambda handle, sat, code: 1575.42e6)

        def _free(self, handle):
            self.freed = True

        def _counts(self, handle, gps, glonass, sbas):
            gps._obj.value, glonass._obj.value, sbas._obj.value = 9, 2, 1
            return 1

        @staticmethod
        def _fill(rs, dts, variance, health):
            for index, value in enumerate((26e6, 1e6, 2e6, 1.0, 2.0, 3.0)):
                rs[index] = value
            dts[0], dts[1] = 1e-5, 2e-12
            variance._obj.value, health._obj.value = 4.0, 0
            return 1

        def _state(self, handle, week, tow, sat, rs, dts, variance, health):
            return self._fill(rs, dts, variance, health)

        def _transmit_state(self, handle, week, tow, sat, pseudorange, rs, dts, variance, health):
            assert pseudorange == pytest.approx(22e6)
            return self._fill(rs, dts, variance, health)

        @staticmethod
        def _ephemeris_audit(handle, week, tow, sat, age, toe_week, toe_tow,
                             toc_week, toc_tow, health, iode):
            age._obj.value = 100.0
            toe_week._obj.value = toc_week._obj.value = week
            toe_tow._obj.value = toc_tow._obj.value = tow - 100.0
            health._obj.value = 0
            iode._obj.value = 12
            return 1

    fake = FakeLibrary()
    monkeypatch.setattr(ctypes, "CDLL", lambda _path: fake)
    bridge = tmp_path / "bridge.so"
    nav1, nav2 = tmp_path / "one.nav", tmp_path / "two.nav"
    for path in (bridge, nav1, nav2):
        path.write_bytes(b"test")
    with RtklibBroadcastProvider(bridge, [nav1, nav2]) as provider:
        assert provider.ephemeris_counts == {"gps_gal_bds_qzs": 9, "glonass": 2, "sbas": 1}
        state = provider.state(SignalIdentity(0, 7, 0, 0), 2400, 100.0, 22e6)
        assert np.linalg.norm(state.position_ecef_m) > 20e6
        assert state.clock_bias_s == pytest.approx(1e-5)
        audit = provider.ephemeris_audit(SignalIdentity(0, 7, 0, 0), 2400, 100.0)
        assert audit.signed_age_seconds == pytest.approx(100.0)
        assert audit.iode == 12
        assert provider.frequency_hz(SignalIdentity(0, 7, 0, 0)) == pytest.approx(1575.42e6)
    assert fake.freed
    build_gps_l1_double_difference_model,
    decode_nav_sat,
    gps_l1_code_spp,
