from __future__ import annotations

import datetime as dt
import decimal
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.horizontal_literature.ginav2021 import imu_adapter
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.imu_adapter import (
    Go2ImuRecord,
    build_format2_increments,
    flu_to_rfu,
    rfu_to_flu,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.rinex_adapter import (
    RinexAdapterError,
    _navigation_time_inventory,
    audit_rinex_pair,
    build_convbin_command,
    inventory_ubx_message_roles,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.source import (
    ForbiddenInputError,
    assert_gnss1_only_path,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.time_contract import (
    GpsTime,
    NavPvtTime,
    RawxTime,
    RinexEpoch,
    TimeContractError,
    associate_nav_pvt_by_stream_order,
    five_phase_row_conservation_audit,
    gpst_calendar_to_gps,
    gps_to_gpst_calendar,
    gps_to_utc_unix_ns,
    normalize_rinex_epochs,
    official_epoch_acceptance_audit,
    parse_rinex_epochs,
    prove_single_constant_normalization,
    utc_unix_ns_to_gps,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.transaction import (
    _official_run_epoch_inventory,
)


def _header_line(prefix: str, label: str) -> str:
    return f"{prefix:<60}{label}\n"


def _observation_text_for(
    system: str,
    satellite: str,
    observation_types: tuple[str, ...],
    epoch_values: tuple[dict[str, float], ...],
) -> str:
    body: list[str] = []
    for epoch_index, values in enumerate(epoch_values):
        body.append(
            f"> 2022 01 01 00 00 {epoch_index:2d}.0000000  0  1\n"
        )
        fields = "".join(
            f"{values.get(observation_type, 0.0):14.3f}  "
            for observation_type in observation_types
        )
        body.append(satellite + fields + "\n")
    return "".join(
        (
            _header_line("3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE"),
            _header_line(
                f"{system}  {len(observation_types):3d} "
                + " ".join(observation_types),
                "SYS / # / OBS TYPES",
            ),
            _header_line("", "END OF HEADER"),
            *body,
        )
    )


def _observation_text(*, phase_value: float = 20.0) -> str:
    types = ("C1C", "L1C", "D1C", "S1C")
    values = {
        "C1C": 22_000_000.0,
        "L1C": phase_value,
        "D1C": -123.0,
        "S1C": 45.0,
    }
    return _observation_text_for("G", "G01", types, (values, values))


def _nav_field(value: float | int) -> str:
    return f"{float(value):19.12E}".replace("E", "D")


def _navigation_record(
    satellite: str,
    *,
    toc: tuple[int, int, int, int, int, int] = (2022, 1, 1, 0, 0, 0),
    toe_week: int | None = None,
    toe_sow: float | None = None,
    galileo_code: int = 0,
) -> str:
    default_toe = gpst_calendar_to_gps(
        2022, 1, 1, 0, 0, decimal.Decimal("0")
    )
    short_record = satellite.startswith(("R", "S"))
    data = [0.0] * (15 if short_record else 31)
    if not short_record:
        data[11] = default_toe.sow_seconds if toe_sow is None else toe_sow
        data[20] = galileo_code
        data[21] = default_toe.week if toe_week is None else toe_week
    year, month, day, hour, minute, second = toc
    first = (
        f"{satellite} {year:04d} {month:02d} {day:02d} "
        f"{hour:02d} {minute:02d} {second:02d}"
        + "".join(_nav_field(value) for value in data[:3]) + "\n"
    )
    continuation = "".join(
        "    " + "".join(_nav_field(value) for value in data[index:index + 4]) + "\n"
        for index in range(3, len(data), 4)
    )
    return first + continuation


def _navigation_text(
    *,
    toc: tuple[int, int, int, int, int, int] = (2022, 1, 1, 0, 0, 0),
    toe_week: int | None = None,
    toe_sow: float | None = None,
    satellite: str = "G01",
) -> str:
    return "".join(
        (
            _header_line("3.04           NAVIGATION DATA     M", "RINEX VERSION / TYPE"),
            _header_line("", "END OF HEADER"),
            _navigation_record(
                satellite, toc=toc, toe_week=toe_week, toe_sow=toe_sow
            ),
        )
    )


def test_gnss1_only_denylist_and_lossless_convbin_command(tmp_path: Path) -> None:
    assert_gnss1_only_path(tmp_path / "gnss1-raw.csv")
    with pytest.raises(ForbiddenInputError):
        assert_gnss1_only_path(tmp_path / "gnss2-raw.csv")
    command = build_convbin_command(
        tmp_path / "pinned-convbin", tmp_path / "GNSS1.ubx",
        tmp_path / "GNSS1.rnx", tmp_path / "GNSS1.nav",
    )
    assert command[command.index("-v") + 1] == "3.04"
    assert "-ti" not in command and "-y" not in command and "-mask" not in command


def test_rinex_adapter_counts_actual_signals_and_ephemeris_coverage(tmp_path: Path) -> None:
    observation = tmp_path / "GNSS1.rnx"
    navigation = tmp_path / "GNSS1.nav"
    observation.write_text(_observation_text(), encoding="ascii")
    navigation.write_text(_navigation_text(), encoding="ascii")
    audit = audit_rinex_pair(observation, navigation)
    assert audit["epoch_count"] == 2
    assert audit["unique_satellite_count"] == 1
    assert audit["selected_navsys"] == "G"
    assert audit["selected_nfreq"] == 1
    gps = audit["per_system"]["G"]
    assert gps["nonzero_observation_counts"]["C1C"] == 2
    assert gps["nonzero_observation_counts"]["L1C"] == 2
    assert gps["valid_band_satellites"] == {"1": ["G01"]}
    assert gps["source_ephemeris_coverage_at_every_experiment_epoch"] is True
    assert gps["source_ephemeris_coverage_by_matching_satellite_all_epochs"] == {
        "G01": True
    }
    assert gps["source_ephemeris_time_basis"] == (
        "GINav_eph.toe_from_RINEX_broadcast_Toe_and_week"
    )
    assert gps["toc_used_as_ephemeris_age_quantity"] is False


def test_rinex_ephemeris_coverage_uses_toe_not_toc(tmp_path: Path) -> None:
    observation = tmp_path / "GNSS1.rnx"
    navigation = tmp_path / "GNSS1.nav"
    observation.write_text(_observation_text(), encoding="ascii")
    near = gpst_calendar_to_gps(
        2022, 1, 1, 0, 0, decimal.Decimal("0")
    )
    # Toc is twelve hours away, but the broadcast Toe is exactly at the
    # experiment epoch. A Toc-based audit would falsely reject this record.
    navigation.write_text(
        _navigation_text(
            toc=(2021, 12, 31, 12, 0, 0),
            toe_week=near.week,
            toe_sow=near.sow_seconds,
        ),
        encoding="ascii",
    )
    audit = audit_rinex_pair(observation, navigation)
    assert audit["per_system"]["G"][
        "source_ephemeris_coverage_at_every_experiment_epoch"
    ] is True

    # Conversely, a near Toc must not conceal a Toe outside MAXDTOE.
    navigation.write_text(
        _navigation_text(
            toe_week=near.week,
            toe_sow=near.sow_seconds + 10_000,
        ),
        encoding="ascii",
    )
    with pytest.raises(RinexAdapterError, match="no GINav-supported constellation"):
        audit_rinex_pair(observation, navigation)


def test_navigation_toe_decoding_matches_bds_glonass_and_galileo_source(
    tmp_path: Path,
) -> None:
    navigation = tmp_path / "mixed.nav"
    gps_toe = gpst_calendar_to_gps(
        2022, 1, 1, 0, 0, decimal.Decimal("0")
    )
    navigation.write_text(
        _header_line("3.04           NAVIGATION DATA     M", "RINEX VERSION / TYPE")
        + _header_line("", "END OF HEADER")
        + _navigation_record(
            "C01", toc=(2006, 1, 1, 0, 0, 0), toe_week=0, toe_sow=0
        )
        + _navigation_record("R01", toc=(2022, 1, 1, 0, 7, 40))
        + _navigation_record(
            "E01", toe_week=gps_toe.week, toe_sow=gps_toe.sow_seconds,
            galileo_code=0,
        )
        + _navigation_record(
            "E02", toe_week=gps_toe.week, toe_sow=gps_toe.sow_seconds,
            galileo_code=1 << 9,
        ),
        encoding="ascii",
    )
    inventory = _navigation_time_inventory(navigation)
    assert inventory["C01"] == (
        1356 * 604800 * 1_000_000_000 + 14 * 1_000_000_000,
    )
    rounded_glonass = gpst_calendar_to_gps(
        2022, 1, 1, 0, 15, decimal.Decimal("18")
    )
    assert inventory["R01"] == (
        rounded_glonass.week * 604800 * 1_000_000_000
        + rounded_glonass.sow_nanoseconds,
    )
    assert "E01" not in inventory
    assert inventory["E02"] == (
        gps_toe.week * 604800 * 1_000_000_000 + gps_toe.sow_nanoseconds,
    )


def test_sbas_record_is_skipped_without_consuming_qzss_adjweek_record(
    tmp_path: Path,
) -> None:
    navigation = tmp_path / "sbas_qzss.nav"
    qzss_toc = gpst_calendar_to_gps(
        2022, 1, 2, 0, 0, decimal.Decimal("5")
    )
    navigation.write_text(
        _header_line("3.04           NAVIGATION DATA     M", "RINEX VERSION / TYPE")
        + _header_line("", "END OF HEADER")
        + _navigation_record("S01", toc=(2022, 1, 2, 0, 0, 0))
        + _navigation_record(
            "J01", toc=(2022, 1, 2, 0, 0, 5),
            toe_week=qzss_toc.week, toe_sow=604_790,
        ),
        encoding="ascii",
    )
    inventory = _navigation_time_inventory(navigation)
    assert "S01" not in inventory
    assert inventory["J01"] == (
        (qzss_toc.week - 1) * 604800 * 1_000_000_000
        + 604_790 * 1_000_000_000,
    )


def test_rinex_adapter_rejects_declared_but_zero_phase(tmp_path: Path) -> None:
    observation = tmp_path / "GNSS1.rnx"
    navigation = tmp_path / "GNSS1.nav"
    observation.write_text(_observation_text(phase_value=0.0), encoding="ascii")
    navigation.write_text(_navigation_text(), encoding="ascii")
    with pytest.raises(RinexAdapterError, match="no GINav-supported constellation"):
        audit_rinex_pair(observation, navigation)


def test_official_tracking_family_selection_rejects_cross_family_pairing(
    tmp_path: Path,
) -> None:
    observation = tmp_path / "GNSS1.rnx"
    navigation = tmp_path / "GNSS1.nav"
    types = ("C1C", "L1W")
    values = {"C1C": 22_000_000.0, "L1W": 20.0}
    observation.write_text(
        _observation_text_for("G", "G01", types, (values, values)),
        encoding="ascii",
    )
    navigation.write_text(_navigation_text(), encoding="ascii")
    with pytest.raises(RinexAdapterError, match="no GINav-supported constellation"):
        audit_rinex_pair(observation, navigation)


def test_official_tracking_priority_and_pinned_slot1_frequency_are_frozen(
    tmp_path: Path,
) -> None:
    observation = tmp_path / "GNSS1.rnx"
    navigation = tmp_path / "GNSS1.nav"
    types = ("C1C", "L1C", "C1W", "L1W", "C2C", "L2C")
    values = {name: float(index + 1) for index, name in enumerate(types)}
    observation.write_text(
        _observation_text_for("G", "G01", types, (values, values)),
        encoding="ascii",
    )
    navigation.write_text(_navigation_text(), encoding="ascii")
    audit = audit_rinex_pair(observation, navigation)
    inventory = audit["per_system"]["G"]["official_used_slot_inventory"]
    assert inventory["decoder_selected_signal_by_raw_slot"]["1"] == "1C"
    assert inventory["decoder_selected_signal_by_raw_slot"]["2"] == "2C"
    assert audit["diagnostic_maximum_contiguous_usable_output_slots"] == 2
    assert audit["diagnostic_maximum_used_for_nfreq_selection"] is False
    assert audit["diagnostic_maximum_role"] == (
        "DIAGNOSTIC_ONLY_NOT_NFREQ_SELECTION"
    )
    assert audit["selected_nfreq"] == 1
    assert audit["selected_nfreq_source"] == (
        "pinned_official_config_nfreq_1_with_prange_P_1_and_"
        "tdcp_current_previous_L_1_consumers"
    )


def test_code_phase_must_share_current_epoch_and_phase_must_have_prior_epoch(
    tmp_path: Path,
) -> None:
    observation = tmp_path / "GNSS1.rnx"
    navigation = tmp_path / "GNSS1.nav"
    types = ("C1C", "L1C")
    observation.write_text(
        _observation_text_for(
            "G", "G01", types,
            ({"C1C": 22_000_000.0}, {"L1C": 20.0}),
        ),
        encoding="ascii",
    )
    navigation.write_text(_navigation_text(), encoding="ascii")
    with pytest.raises(RinexAdapterError, match="no GINav-supported constellation"):
        audit_rinex_pair(observation, navigation)


def test_bds_post_adjobs_remap_rejects_b1c_only_bds3_and_accepts_b2i_slot1(
    tmp_path: Path,
) -> None:
    navigation = tmp_path / "GNSS1.nav"
    gps_time = gpst_calendar_to_gps(
        2022, 1, 1, 0, 0, decimal.Decimal("0")
    )
    navigation.write_text(
        _navigation_text(
            satellite="C19",
            toe_week=gps_time.week - 1356,
            toe_sow=gps_time.sow_seconds - 14,
        ),
        encoding="ascii",
    )
    observation = tmp_path / "GNSS1.rnx"
    b1c = {"C1D": 22_000_000.0, "L1D": 20.0}
    observation.write_text(
        _observation_text_for("C", "C19", ("C1D", "L1D"), (b1c, b1c)),
        encoding="ascii",
    )
    with pytest.raises(RinexAdapterError, match="no GINav-supported constellation"):
        audit_rinex_pair(observation, navigation)

    b2i = {"C2I": 22_000_000.0, "L2I": 20.0}
    observation.write_text(
        _observation_text_for("C", "C19", ("C2I", "L2I"), (b2i, b2i)),
        encoding="ascii",
    )
    audit = audit_rinex_pair(observation, navigation)
    inventory = audit["per_system"]["C"]["official_used_slot_inventory"]
    assert inventory["decoder_selected_signal_by_raw_slot"]["1"] == "2I"
    assert inventory["per_satellite_post_adjobs_output_slots"]["C19"]["1"][
        "raw_decoder_slot"
    ] == 1
    assert inventory["p1_l1_usable_satellites"] == ["C19"]
    assert audit["selected_navsys"] == "C"


def test_ubx_inventory_assigns_every_message_and_exclusion_explicit_reason() -> None:
    audit = inventory_ubx_message_roles(
        {"02-15": 3, "02-13": 4, "01-07": 2, "0A-04": 1},
        discarded_byte_count=5,
        checksum_failure_count=6,
    )
    assert audit["every_observed_message_class_has_explicit_role_and_reason"] is True
    rows = {row["ubx_class_id"]: row for row in audit["message_classes"]}
    assert rows["02-15"]["excluded_from_ginav_measurement_interface"] is False
    assert rows["02-13"]["excluded_from_ginav_measurement_interface"] is False
    assert rows["01-07"]["excluded_from_ginav_measurement_interface"] is True
    assert rows["0A-04"]["reason"]
    assert audit["discarded_nonmessage_reason"]
    assert audit["checksum_failure_reason"]


def test_flu_rfu_current_sample_format2_drops_invalid_dt_with_conservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert flu_to_rfu((1.0, 2.0, 3.0)) == (-2.0, 1.0, 3.0)
    assert rfu_to_flu((-2.0, 1.0, 3.0)) == (1.0, 2.0, 3.0)
    monkeypatch.setattr(imu_adapter, "GO2_COMPLETE_RECORDS", 6)
    second = 1_500_000_000 * 1_000_000_000
    records = (
        Go2ImuRecord(second, (1.0, 2.0, 3.0), (4.0, 5.0, 6.0)),
        Go2ImuRecord(second + 10_000_000, (10.0, 20.0, 30.0), (40.0, 50.0, 60.0)),
        Go2ImuRecord(second + 10_000_000, (11.0, 21.0, 31.0), (41.0, 51.0, 61.0)),
        Go2ImuRecord(second + 5_000_000, (12.0, 22.0, 32.0), (42.0, 52.0, 62.0)),
        Go2ImuRecord(second + 210_000_000, (100.0, 200.0, 300.0), (400.0, 500.0, 600.0)),
        Go2ImuRecord(second + 220_000_000, (7.0, 8.0, 9.0), (10.0, 11.0, 12.0)),
    )
    increments, audit = build_format2_increments(records)
    assert len(increments) == 2
    assert increments[0].delta_angle_rfu_rad == pytest.approx((-0.2, 0.1, 0.3))
    assert increments[1].delta_angle_rfu_rad == pytest.approx((-0.08, 0.07, 0.09))
    assert audit["invalid_dt_lte_0_skipped_count"] == 2
    assert audit["invalid_dt_gt_0p1_skipped_count"] == 1
    assert audit["invalid_dt_total_skipped_count"] == 3
    assert audit["nonpositive_dt_count"] == 2
    assert audit["candidate_interval_count"] == 5
    assert audit["output_row_count"] == 2
    assert audit["interval_outcome_conservation_pass"] is True
    assert audit["input_time_strictly_monotonic"] is False
    assert audit["output_time_strictly_monotonic"] is True
    assert (
        audit["output_row_count"]
        + audit["invalid_dt_lte_0_skipped_count"]
        + audit["invalid_dt_gt_0p1_skipped_count"]
        == audit["candidate_interval_count"]
    )
    assert audit["increment_policy"] == "current_sample_times_dt"
    assert audit["sqrt_dt_preprocessing"] is False
    assert audit["first_output_gps_sow_seconds"] != audit["first_gps_sow_seconds"]


def test_gps_week_sow_round_trip() -> None:
    unix_ns = 1_700_000_000_123_456_789
    gps = utc_unix_ns_to_gps(unix_ns)
    assert gps_to_utc_unix_ns(gps.week, gps.sow_nanoseconds) == unix_ns
    epoch = utc_unix_ns_to_gps(315_964_800 * 1_000_000_000)
    assert epoch == GpsTime(0, 0)


def test_official_run_epoch_inventory_is_windowed_matched_and_conserved(
    tmp_path: Path,
) -> None:
    start = dt.datetime(2022, 1, 1, 0, 0, 0)
    stop = start + dt.timedelta(seconds=3)
    base = gpst_calendar_to_gps(
        2022, 1, 1, 0, 0, decimal.Decimal("0")
    )
    epochs = (
        RinexEpoch(0, 1, "", base, "0.000", 0, 0, 1),
        RinexEpoch(
            1, 2, "", GpsTime(base.week, base.sow_nanoseconds + 1_000_000_000),
            "1.000", 0, 0, 1,
        ),
        RinexEpoch(
            2, 3, "", GpsTime(base.week, base.sow_nanoseconds + 2_000_000_000),
            "2.000", 0, 0, 1,
        ),
        RinexEpoch(
            3, 4, "", GpsTime(base.week, base.sow_nanoseconds + 2_500_000_000),
            "2.500", 500_000_000, 0, 1,
        ),
        RinexEpoch(
            4, 5, "", GpsTime(base.week, base.sow_nanoseconds + 4_000_000_000),
            "4.000", 0, 0, 1,
        ),
    )
    imu = tmp_path / "IMU.csv"
    imu.write_text(
        "gps_week,gps_sow,delta_angle_r,delta_angle_f,delta_angle_u,"
        "delta_velocity_r,delta_velocity_f,delta_velocity_u\n"
        f"{base.week},{(base.sow_nanoseconds + 2_000_000) / 1_000_000_000:.9f},0,0,0,0,0,0\n"
        f"{base.week},{(base.sow_nanoseconds + 1_002_000_000) / 1_000_000_000:.9f},0,0,0,0,0,0\n"
        f"{base.week},{(base.sow_nanoseconds + 2_010_000_000) / 1_000_000_000:.9f},0,0,0,0,0,0\n",
        encoding="ascii",
    )
    audit = _official_run_epoch_inventory(
        epochs, imu, start_time_gpst=start, end_time_gpst=stop,
        sample_rate_hz=100,
    )
    assert audit["input_gnss_epoch_count"] == 4
    assert audit["in_window_integer_epoch_count"] == 3
    assert audit["in_window_noninteger_rejected_count"] == 1
    assert audit["accepted_official_gnss_epoch_count"] == 2
    assert audit["in_window_integer_unmatched_imu_count"] == 1
    assert audit["conservation_pass"] is True


def test_no_search_constant_time_normalization_and_row_ledger(tmp_path: Path) -> None:
    first = GpsTime(2200, 100_998_000_000)
    second = GpsTime(2200, 101_998_000_000)
    epochs = (
        RinexEpoch(0, 4, "", first, "40.998", 998_000_000, 0, 1),
        RinexEpoch(1, 6, "", second, "41.998", 998_000_000, 0, 1),
    )
    rawx = (RawxTime(10, 2200, first.sow_nanoseconds), RawxTime(30, 2200, second.sow_nanoseconds))
    pvt = (NavPvtTime(11, 101_000, True), NavPvtTime(31, 102_000, True))
    proof = prove_single_constant_normalization(rawx, pvt, epochs)
    assert proof["constant_offset_nanoseconds"] == 2_000_000
    assert proof["candidate_offset_search_performed"] is False
    assert [row["authoritative_message_sequence"] for row in proof["ledger"]] == [11, 31]

    # Rebuild equivalent calendar epoch lines to exercise serialized rewrite.
    calendar_first = gpst_calendar_to_gps(
        2022, 3, 6, 0, 1, decimal.Decimal("40.998")
    )
    calendar_second = gpst_calendar_to_gps(
        2022, 3, 6, 0, 1, decimal.Decimal("41.998")
    )
    calendar_epochs = (
        RinexEpoch(0, 4, "", calendar_first, "40.998", 998_000_000, 0, 1),
        RinexEpoch(1, 6, "", calendar_second, "41.998", 998_000_000, 0, 1),
    )
    calendar_rawx = (
        RawxTime(10, calendar_first.week, calendar_first.sow_nanoseconds),
        RawxTime(30, calendar_second.week, calendar_second.sow_nanoseconds),
    )
    calendar_pvt = (
        NavPvtTime(11, 101_000, True), NavPvtTime(31, 102_000, True),
    )
    calendar_proof = prove_single_constant_normalization(
        calendar_rawx, calendar_pvt, calendar_epochs
    )
    source = tmp_path / "literal.rnx"
    source.write_text(
        _header_line("3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE")
        + _header_line("", "END OF HEADER")
        + "> 2022 03 06 00 01 40.9980000  0  0\n"
        + "> 2022 03 06 00 01 41.9980000  0  0\n",
        encoding="ascii",
    )
    destination = tmp_path / "normalized.rnx"
    rows = normalize_rinex_epochs(source, destination, calendar_proof)
    assert len(rows) == 2
    assert "42.0000000" in destination.read_text(encoding="ascii")


def test_causal_association_canonicalizes_semantic_duplicate_and_ignores_pre_first() -> None:
    rawx = (
        RawxTime(10, 2200, 100_998_000_000),
        RawxTime(20, 2200, 101_998_000_000),
    )
    pvt = (
        NavPvtTime(9, 999_000, True),
        NavPvtTime(11, 101_000, True),
        NavPvtTime(12, 101_000, True),
        NavPvtTime(25, 102_000, True),
    )
    audit = associate_nav_pvt_by_stream_order(rawx, pvt)
    assert audit["pre_first_nav_pvt_ignored_count"] == 1
    assert audit["unique_association_count"] == 1
    assert audit["semantic_duplicate_association_count"] == 1
    assert audit["conflicting_association_count"] == 0
    assert audit["missing_association_count"] == 0
    assert audit["rows"][0]["canonical_message_sequence"] == 11
    assert audit["rows"][1]["window_ends_at_eof"] is True
    assert audit["rows"][1]["canonical_message_sequence"] == 25


def test_causal_association_true_conflict_and_missing_fail_closed() -> None:
    rawx = (
        RawxTime(10, 2200, 100_998_000_000),
        RawxTime(20, 2200, 101_998_000_000),
    )
    conflict = associate_nav_pvt_by_stream_order(
        rawx,
        (NavPvtTime(11, 101_000, True), NavPvtTime(12, 101_001, True)),
    )
    assert conflict["conflicting_association_count"] == 1
    assert conflict["missing_association_count"] == 1
    epochs = (
        RinexEpoch(0, 1, "", GpsTime(2200, 100_998_000_000), "0.998", 998_000_000, 0, 1),
        RinexEpoch(1, 2, "", GpsTime(2200, 101_998_000_000), "1.998", 998_000_000, 0, 1),
    )
    with pytest.raises(TimeContractError, match="missing"):
        prove_single_constant_normalization(
            rawx, (NavPvtTime(11, 101_000, True),), epochs
        )
    with pytest.raises(TimeContractError, match="conflicting semantic signatures"):
        prove_single_constant_normalization(
            rawx,
            (
                NavPvtTime(11, 101_000, True),
                NavPvtTime(12, 101_001, True),
                NavPvtTime(21, 102_000, True),
            ),
            epochs,
        )


def test_signed_modulo_week_relation_and_five_phase_row_conservation() -> None:
    week_ns = 604_800 * 1_000_000_000
    rawx = (RawxTime(10, 2200, week_ns - 2_000_000),)
    epochs = (
        RinexEpoch(
            0, 1, "", GpsTime(2200, week_ns - 2_000_000),
            "59.998", 998_000_000, 0, 1,
        ),
    )
    proof = prove_single_constant_normalization(
        rawx, (NavPvtTime(11, 0, True),), epochs
    )
    assert proof["constant_offset_nanoseconds"] == 2_000_000
    normalized_rows = ({"epoch_index": 0},)
    selected = (
        RinexEpoch(0, 1, "", GpsTime(2201, 0), "0.000", 0, 0, 1),
    )
    audit = five_phase_row_conservation_audit(
        rawx_epoch_count=1,
        original_rinex_epochs=epochs,
        proof=proof,
        normalized_rows=normalized_rows,
        selected_rinex_epochs=selected,
    )
    assert audit["pass"] is True
    assert audit["deleted_or_merged_epoch_count"] == 0


def test_1509_file_rows_preserve_five_phase_distribution_at_plus_2ms(
    tmp_path: Path,
) -> None:
    count = 1509
    normalized_start_ns = 100_000 * 1_000_000_000
    rawx = tuple(
        RawxTime(
            index * 3,
            2200,
            normalized_start_ns + index * 200_000_000 - 2_000_000,
        )
        for index in range(count)
    )
    pvt = tuple(
        NavPvtTime(
            index * 3 + 1,
            (normalized_start_ns + index * 200_000_000) // 1_000_000,
            True,
        )
        for index in range(count)
    )
    lines = [
        _header_line("3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE"),
        _header_line("", "END OF HEADER"),
    ]
    for item in rawx:
        year, month, day, hour, minute, second = gps_to_gpst_calendar(
            GpsTime(item.week, item.tow_nanoseconds)
        )
        lines.append(
            f"> {year:04d} {month:02d} {day:02d} {hour:02d} {minute:02d} "
            f"{float(second):10.7f}  0  0\n"
        )
    source = tmp_path / "literal_1509.rnx"
    destination = tmp_path / "normalized_1509.rnx"
    source.write_text("".join(lines), encoding="ascii")
    epochs = parse_rinex_epochs(source)
    proof = prove_single_constant_normalization(rawx, pvt, epochs)
    rows = normalize_rinex_epochs(source, destination, proof)
    selected = parse_rinex_epochs(destination)
    assert proof["selected_epoch_count"] == 1509
    assert proof["constant_offset_nanoseconds"] == 2_000_000
    assert [row["epoch_index"] for row in proof["ledger"]] == list(range(1509))
    assert proof["association_audit"]["unique_association_count"] == 1509
    histogram: dict[int, int] = {}
    for epoch in selected:
        histogram[epoch.fractional_nanoseconds] = (
            histogram.get(epoch.fractional_nanoseconds, 0) + 1
        )
    assert histogram == {
        0: 302,
        200_000_000: 302,
        400_000_000: 302,
        600_000_000: 302,
        800_000_000: 301,
    }
    eligibility = official_epoch_acceptance_audit(selected)
    assert eligibility["literal_accepted_epoch_count"] == 302
    assert eligibility["literal_rejected_noninteger_epoch_count"] == 1207
    assert eligibility["deleted_epoch_count"] == 0
    assert [row["official_fractional_nanoseconds_after"] for row in rows] == [
        epoch.fractional_nanoseconds for epoch in selected
    ]
    audit = five_phase_row_conservation_audit(
        rawx_epoch_count=count,
        original_rinex_epochs=epochs,
        proof=proof,
        normalized_rows=rows,
        selected_rinex_epochs=selected,
    )
    assert audit["pass"] is True
    assert audit["selected_rinex_official_accepted_count"] == 302
    assert audit["selected_rinex_official_rejected_count"] == 1207
    assert audit["accepted_plus_rejected_equals_input"] is True
    assert audit["deleted_or_merged_epoch_count"] == 0
    assert all(row["normalization_retained_epoch_count"] == 1509 for row in rows)
    assert all(row["normalization_deleted_or_merged_epoch_count"] == 0 for row in rows)
