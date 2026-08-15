import csv
import ctypes
import math
import statistics
import struct
from pathlib import Path

import numpy as np
import pytest
import yaml

import legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend as backend

from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import (
    RawBackendError,
    DoubleDifferenceStageError,
    HALF_CYCLE_CONTRACT,
    RawxEpoch,
    RawxMeasurement,
    RtklibBroadcastProvider,
    SatelliteState,
    SignalIdentity,
    TrackingContinuity,
    build_gps_l1_double_difference_model,
    correlated_dd_covariance,
    dd_matrix_condition_diagnostics,
    decode_nav_hpposecef,
    decode_nav_sat,
    decode_rawx,
    decode_sfrbx,
    gps_l1_code_spp,
    gps_l1_epoch_accounting,
    integer_compatible_carrier_cycles,
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
    tracking_epoch_summary,
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
    first_flags = continuity.update(
        1, _epoch(1.0), _measurement(lock=1000),
        ambiguity_reinitialized_by_method=True,
    )
    assert first_flags.first_observation
    assert first_flags.ambiguity_reinitialized_by_method
    assert not first_flags.cycle_slip and not first_flags.arc_reset
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
    repeated_invalid = continuity.update(1, _epoch(4.5), _measurement(lock=35, trk=0x01))
    assert not repeated_invalid.cycle_slip and not repeated_invalid.arc_reset
    restored = continuity.update(1, _epoch(5.0), _measurement(lock=40, trk=0x07))
    assert restored.carrier_valid and restored.arc_reset
    clock = continuity.update(1, _epoch(6.0, status=0x02), _measurement(lock=50))
    assert clock.receiver_clock_reset and clock.arc_reset and not clock.cycle_slip

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


def test_nav_hpposecef_units_bounds_and_reconstruction(tmp_path):
    payload = (
        bytes((0, 1, 2, 3))
        + struct.pack("<Iiii", 123456, 637813700, -12345, 6789)
        + struct.pack("<bbbBI", 99, -99, 1, 7, 250)
    )
    epoch = decode_nav_hpposecef(payload)
    np.testing.assert_allclose(
        epoch.position_ecef_m,
        [6_378_137.0099, -123.4599, 67.8901],
        atol=1e-10,
    )
    assert epoch.position_accuracy_m == pytest.approx(0.025)
    assert epoch.reserved1 == b"\x01\x02\x03" and epoch.reserved2 == 7

    frame = _ubx_frame(0x01, 0x13, payload)
    source = tmp_path / "raw.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["data"])
        writer.writeheader()
        writer.writerow({"data": repr(frame)})
    reconstruction = reconstruct_ubx_stream(source)
    assert reconstruction.message_counts == {"01-13": 1}
    assert reconstruction.nav_hpposecef_epochs == (epoch,)
    assert reconstruction.nav_hpposecef_semantic_decode_enabled is True

    opaque = reconstruct_ubx_stream(
        source, decode_nav_hpposecef_semantics=False,
    )
    assert opaque.stream == frame
    assert opaque.message_counts == {"01-13": 1}
    assert opaque.nav_hpposecef_epochs == ()
    assert opaque.nav_hpposecef_semantic_decode_enabled is False

    invalid_hp = bytearray(payload)
    invalid_hp[20] = 100
    invalid_source = tmp_path / "invalid-hpposecef.csv"
    invalid_frame = _ubx_frame(0x01, 0x13, bytes(invalid_hp))
    with invalid_source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["data"])
        writer.writeheader()
        writer.writerow({"data": repr(invalid_frame)})
    opaque_invalid = reconstruct_ubx_stream(
        invalid_source, decode_nav_hpposecef_semantics=False,
    )
    assert opaque_invalid.stream == invalid_frame
    assert opaque_invalid.nav_hpposecef_epochs == ()

    with pytest.raises(RawBackendError, match="-99..99"):
        decode_nav_hpposecef(bytes(invalid_hp))
    with pytest.raises(RawBackendError, match="boundary"):
        decode_nav_hpposecef(payload[:-1])


class _GeometryProvider:
    status = "SYNTHETIC_TEST_ONLY"

    def __init__(self, positions):
        self.positions = positions

    def state(self, identity, gps_week, gps_tow_seconds, pseudorange_m=None):
        return SatelliteState(np.asarray(self.positions[identity], dtype=float), np.zeros(3),
                              health=0)


def test_no_false_zero_common_raw_epochs():
    measurements1 = tuple(
        _measurement(sv, trk=(0x0F if sv <= 3 else (0x03 if sv == 4 else 0x01)))
        for sv in range(1, 6)
    )
    measurements2 = tuple(
        _measurement(sv, trk=(0x0F if sv <= 4 else 0x03)) for sv in range(1, 6)
    )
    accounting = gps_l1_epoch_accounting(
        _epoch(10.0, measurements1), _epoch(10.0, measurements2)
    )
    assert accounting.common_raw_satellite_count == 5
    assert accounting.common_pr_valid_satellite_count == 5
    assert accounting.common_cp_valid_satellite_count == 4
    assert accounting.common_pr_cp_valid_satellite_count == 4
    assert accounting.common_half_cycle_valid_satellite_count == 3
    assert accounting.common_integer_compatible_satellite_count == 3
    with pytest.raises(DoubleDifferenceStageError) as caught:
        build_gps_l1_double_difference_model(
            _epoch(10.0, measurements1), _epoch(10.0, measurements2),
            _GeometryProvider({}), [6_378_137.0, 0.0, 0.0],
        )
    assert caught.value.code == "INSUFFICIENT_HALF_CYCLE_VALID"
    assert caught.value.accounting.common_raw_satellite_count == 5


def test_satellite_state_failure_does_not_zero_raw_count():
    class FailedStateProvider:
        status = "TEST_FAILURE"

        def state(self, identity, gps_week, gps_tow_seconds, pseudorange_m=None):
            raise RawBackendError(f"no state for {identity}")

    measurements = tuple(_measurement(sv, trk=0x0F) for sv in range(1, 6))
    first, second = _epoch(11.0, measurements), _epoch(11.0, measurements)
    with pytest.raises(DoubleDifferenceStageError) as caught:
        build_gps_l1_double_difference_model(
            first, second, FailedStateProvider(), [6_378_137.0, 0.0, 0.0]
        )
    error = caught.value
    assert error.code == "INSUFFICIENT_SATELLITE_STATES"
    assert error.accounting.common_raw_satellite_count == 5
    assert error.accounting.common_integer_compatible_satellite_count == 5
    assert error.accounting.satellite_state_available_count == 0


def test_tracking_flags_are_per_measurement():
    continuity = TrackingContinuity()
    epoch1 = _epoch(20.0, (_measurement(1, lock=100, trk=0x0F),
                           _measurement(2, lock=100, trk=0x01)))
    summary1 = tracking_epoch_summary(
        continuity, 1, epoch1, [SignalIdentity(0, 1, 0, 0)],
        ambiguity_reinitialized_by_method=True,
    )
    assert summary1.measurement_count == 2
    assert summary1.used_carrier_count == 1
    assert summary1.excluded_cp_invalid_count == 1
    assert summary1.excluded_half_cycle_unknown_count == 0
    assert summary1.sub_half_cycle_set_count == 1
    assert summary1.actual_cycle_slip_count == 0
    assert summary1.ambiguity_reinitialized_by_method

    epoch2 = _epoch(21.0, (_measurement(1, lock=10, trk=0x07),
                           _measurement(2, lock=110, trk=0x03)))
    summary2 = tracking_epoch_summary(continuity, 1, epoch2)
    assert summary2.actual_lock_reset_count == 1
    assert summary2.half_cycle_state_change_count == 1
    assert summary2.actual_cycle_slip_count == 2
    assert summary2.excluded_half_cycle_unknown_count == 1


def test_method_reinitialization_is_not_cycle_slip():
    continuity = TrackingContinuity()
    measurement = _measurement(3, lock=500, trk=0x0F)
    first = continuity.update(
        1, _epoch(30.0), measurement,
        ambiguity_reinitialized_by_method=True,
    )
    second = continuity.update(
        1, _epoch(31.0), _measurement(3, lock=600, trk=0x0F),
        ambiguity_reinitialized_by_method=True,
    )
    assert first.ambiguity_reinitialized_by_method and second.ambiguity_reinitialized_by_method
    assert not first.cycle_slip_detected and not second.cycle_slip_detected
    assert not first.arc_reset_due_to_tracking and not second.arc_reset_due_to_tracking


def test_half_cycle_contract_against_ubx_spec():
    assert HALF_CYCLE_CONTRACT.ubx_document_sha256 == (
        "3d6539cd5ab3efe1254c54e4dba25d17421bfe48ac96e633e602d8d214c13668"
    )
    assert HALF_CYCLE_CONTRACT.rtklib_commit == (
        "180043ee24b6d2b168f98b64be15f69d50046b1a"
    )
    subtracted = _measurement(3, trk=0x0F)
    # subHalfCyc reports a correction already present in cpMes.  The pinned
    # RTKLIB RXM-RAWX decoder likewise copies L=cpMes without a second +/-0.5.
    assert integer_compatible_carrier_cycles(subtracted) == subtracted.cp_mes_cycles
    assert strict_raw_tracking_eligible(subtracted)
    with pytest.raises(RawBackendError, match="unresolved"):
        integer_compatible_carrier_cycles(_measurement(3, trk=0x03))


def test_integer_compatibility_diagnostic():
    first = _epoch(40.0, (
        _measurement(1, trk=0x0F),
        _measurement(2, trk=0x07, cp_std=6),
        _measurement(3, trk=0x03),
        _measurement(4, trk=0x0F, cp_std=15),
    ))
    second = _epoch(40.0, (
        _measurement(1, trk=0x07),
        _measurement(2, trk=0x0F, cp_std=6),
        _measurement(3, trk=0x0F),
        _measurement(4, trk=0x0F),
    ))
    accounting = gps_l1_epoch_accounting(first, second)
    assert accounting.common_raw_satellite_count == 4
    assert accounting.common_pr_cp_valid_satellite_count == 4
    assert accounting.common_half_cycle_valid_satellite_count == 3
    assert accounting.common_integer_compatible_satellite_count == 2
    assert accounting.common_rtklib_phase_compatible_satellite_count == 1
    assert tuple(item.sv_id for item in accounting.common_integer_compatible_identities) == (1, 2)


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
    assert model.receiver_order == "GNSS2_MINUS_GNSS1"
    assert model.dd_sign_convention == "(GNSS2-GNSS1)_SATELLITE_MINUS_PIVOT"
    assert model.ambiguity_satellite_identities == model.satellites
    assert len(model.ambiguity_signal_identities) == model.ambiguity_design_m.shape[1]
    conditions = dd_matrix_condition_diagnostics(model)
    assert conditions.raw_design_rank == conditions.unknown_count
    assert conditions.whitened_design_rank == conditions.unknown_count
    assert np.isfinite(conditions.raw_design_condition)
    assert np.isfinite(conditions.whitened_design_condition)


def test_ambiguity_identity_vector_alignment():
    """The model metadata order is exactly the ambiguity-design column order."""
    identities = tuple(SignalIdentity(0, sv, 0, 0) for sv in (3, 7, 11))
    accounting = backend.GpsL1EpochAccounting(
        common_raw_identities=identities,
        common_pr_valid_identities=identities,
        common_cp_valid_identities=identities,
        common_pr_cp_valid_identities=identities,
        common_half_cycle_valid_identities=identities,
        common_integer_compatible_identities=identities,
        satellite_state_available_identities=identities,
        elevation_eligible_identities=identities,
        dd_eligible_identities=identities,
    )
    model = backend.DoubleDifferenceModel(
        pivot=SignalIdentity(0, 2, 0, 0),
        satellites=identities,
        observation_m=np.zeros(6),
        ambiguity_design_m=np.vstack((np.zeros((3, 3)), np.eye(3))),
        baseline_design=np.zeros((6, 3)),
        covariance_m2=np.eye(6),
        elevations_rad={},
        accounting=accounting,
    )
    ambiguity = [1, -2, 3]
    assert [backend.identity_text(item) for item in model.ambiguity_satellite_identities] == [
        "0:3:0:0", "0:7:0:0", "0:11:0:0"
    ]
    assert len(model.ambiguity_satellite_identities) == len(ambiguity)
    assert model.receiver_order == "GNSS2_MINUS_GNSS1"


def test_receiver_clock_reset_resets_arc_without_false_cycle_slip():
    continuity = TrackingContinuity()
    measurement = _measurement(7, trk=0x0F, lock=500)
    continuity.update(1, _epoch(1.0, (measurement,)), measurement)
    reset_epoch = RawxEpoch(2.0, 2408, 18, 0x02, 1, (measurement,))
    flags = continuity.update(1, reset_epoch, measurement)
    assert flags.receiver_clock_reset is True
    assert flags.arc_reset_due_to_tracking is True
    assert flags.cycle_slip_detected is False


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


def _independent_rawx_tracking(stream):
    """Minimal test-only RAWX decoder, independent of the DD builder/decoder."""
    epochs = {}
    cursor = 0
    while cursor < len(stream):
        assert stream[cursor:cursor + 2] == b"\xb5\x62"
        message_class, message_id, length = struct.unpack_from("<BBH", stream, cursor + 2)
        end = cursor + 6 + length
        body = stream[cursor + 2:end]
        first = second = 0
        for value in body:
            first = (first + value) & 0xFF
            second = (second + first) & 0xFF
        assert stream[end:end + 2] == bytes((first, second))
        if (message_class, message_id) == (0x02, 0x15):
            payload = stream[cursor + 6:end]
            tow, week, _leap, count, _rec_stat, version = struct.unpack_from(
                "<dHbBBB", payload
            )
            assert version == 1 and len(payload) == 16 + 32 * count
            tracking = {}
            for index in range(count):
                offset = 16 + 32 * index
                gnss, sv, sig, freq = struct.unpack_from("<BBBB", payload, offset + 20)
                trk_stat = payload[offset + 30]
                tracking[(gnss, sv, sig, freq)] = trk_stat
            assert (week, tow) not in epochs
            epochs[(week, tow)] = tracking
        cursor = end + 2
    return epochs


def test_independent_common_satellite_counts():
    repository = Path(__file__).resolve().parents[2]
    local_config = repository / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
    if not local_config.is_file():
        pytest.skip("ignored Phase1R local data-path configuration is unavailable")
    configured = yaml.safe_load(local_config.read_text(encoding="utf-8"))
    raw_root = Path(configured["paths"]["by2_fix_root"])
    raw_paths = (raw_root / "gnss1-raw.csv", raw_root / "gnss2-raw.csv")
    if not all(path.is_file() for path in raw_paths):
        pytest.skip("hash-locked BY2 raw CSV files are unavailable")

    reconstructions = tuple(reconstruct_ubx_stream(path) for path in raw_paths)
    direct1, direct2 = (
        _independent_rawx_tracking(reconstruction.stream)
        for reconstruction in reconstructions
    )
    keys = sorted(set(direct1) & set(direct2))
    assert len(keys) == 1509
    backend_pairs, failures = pair_epochs(
        reconstructions[0].rawx_epochs, reconstructions[1].rawx_epochs
    )
    assert len(backend_pairs) == 1509 and failures == []
    backend_by_key = {
        (first.gps_week, first.gps_tow_seconds): gps_l1_epoch_accounting(first, second)
        for first, second in backend_pairs
    }

    raw_counts, pr_cp_counts, half_counts = [], [], []
    for key in keys:
        first = {
            identity: status for identity, status in direct1[key].items()
            if (identity[0], identity[2], identity[3]) == (0, 0, 0)
        }
        second = {
            identity: status for identity, status in direct2[key].items()
            if (identity[0], identity[2], identity[3]) == (0, 0, 0)
        }
        common = set(first) & set(second)
        pr_cp = {
            identity for identity in common
            if first[identity] & 0x03 == 0x03 and second[identity] & 0x03 == 0x03
        }
        half = {
            identity for identity in pr_cp
            if first[identity] & 0x04 and second[identity] & 0x04
        }
        direct_counts = (len(common), len(pr_cp), len(half))
        observed = backend_by_key[key]
        backend_counts = (
            observed.common_raw_satellite_count,
            observed.common_pr_cp_valid_satellite_count,
            observed.common_half_cycle_valid_satellite_count,
        )
        if direct_counts != backend_counts:
            dump1 = [(item[1], f"0x{first[item]:02X}") for item in sorted(first)]
            dump2 = [(item[1], f"0x{second[item]:02X}") for item in sorted(second)]
            pytest.fail(
                f"first independent/backend difference at {key}: "
                f"direct={direct_counts} backend={backend_counts}; "
                f"receiver1(sv,trkStat)={dump1}; receiver2(sv,trkStat)={dump2}"
            )
        raw_counts.append(len(common))
        pr_cp_counts.append(len(pr_cp))
        half_counts.append(len(half))

    assert (min(raw_counts), statistics.mean(raw_counts), max(raw_counts),
            sum(value == 0 for value in raw_counts)) == pytest.approx(
                (5, 7.9609012591, 10, 0), abs=1e-10
            )
    assert (min(pr_cp_counts), statistics.mean(pr_cp_counts), max(pr_cp_counts)) == pytest.approx(
        (3, 6.4188204109, 9), abs=1e-10
    )
    assert (min(half_counts), statistics.mean(half_counts), max(half_counts)) == pytest.approx(
        (2, 4.3585155732, 9), abs=1e-10
    )
