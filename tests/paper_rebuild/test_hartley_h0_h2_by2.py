from __future__ import annotations

import csv
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from legsa_gins.paper_rebuild.horizontal_literature import hartley_h0_h2 as h0


def _record(
    index: int,
    *,
    force: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    speed_by_leg: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
) -> h0.HartleyInputRecord:
    positions = (
        (0.30 + index * 1.0e-5, -0.20, -0.31),
        (0.30 + index * 1.0e-5, 0.20, -0.31),
        (-0.30 + index * 1.0e-5, -0.20, -0.31),
        (-0.30 + index * 1.0e-5, 0.20, -0.31),
    )
    speeds = tuple((speed_by_leg[leg], 0.0, 0.0) for leg in range(4))
    return h0.HartleyInputRecord(
        sec=100 + index // 100,
        nanosec=(index % 100) * 10_000_000,
        gyroscope=(0.01, -0.02, 0.03),
        accelerometer=(0.0, 0.0, 9.81),
        foot_force=force,
        foot_position_body=positions,
        foot_speed_body=speeds,  # type: ignore[arg-type]
        gait_type=str((index // 50) % 2),
        mode="1",
    )


def _contact_records(
    *,
    speed_relationship: str = "supportive",
) -> tuple[h0.HartleyInputRecord, ...]:
    rows = []
    for index in range(240):
        block = (index // 30) % 2
        values = tuple(
            (100.0 + 5.0 * leg) if ((block + leg) % 2) else (2.0 + leg)
            for leg in range(4)
        )
        if speed_relationship == "supportive":
            speeds = tuple(1.0 if value > 50.0 else 10.0 for value in values)
        elif speed_relationship == "contradictory":
            speeds = tuple(10.0 if value > 50.0 else 1.0 for value in values)
        else:
            raise AssertionError("unknown synthetic speed relationship")
        rows.append(_record(index, force=values, speed_by_leg=speeds))
    return tuple(rows)


def _physical_record_bytes(
    index: int,
    *,
    foot_speed_count: int = 12,
    omit_field: str | None = None,
    delimiter: bool = True,
    newline: bytes = b"\n",
) -> bytes:
    fields = [
        b"stamp:",
        f"  sec: {100 + index}".encode(),
        f"  nanosec: {index}".encode(),
        b"imu_state:",
        b"  gyroscope: [0.01, 0.02, 0.03]",
        b"  accelerometer: [0, 0, 9.81]",
        b"foot_force: [40, 40, 40, 40]",
        b"foot_position_body: [0.3, -0.2, -0.3, 0.3, 0.2, -0.3, "
        b"-0.3, -0.2, -0.3, -0.3, 0.2, -0.3]",
        b"foot_speed_body: [" + b", ".join([b"0"] * foot_speed_count) + b"]",
        b"gait_type: 1",
        b"mode: 1",
    ]
    if omit_field is not None:
        prefixes = {
            "foot_force": b"foot_force:",
            "gyroscope": b"  gyroscope:",
            "gait_type": b"gait_type:",
        }
        fields = [line for line in fields if not line.startswith(prefixes[omit_field])]
    if delimiter:
        fields.append(b"---")
    return newline.join(fields) + newline


def _fixture_policy(
    payload: bytes,
    *,
    physical_starts: int,
    complete_records: int,
    prefix_end: int | None = None,
    last_complete_timestamp_ns: int | None = None,
) -> h0.CompleteRecordPolicy:
    return h0.CompleteRecordPolicy(
        policy_id=h0.BY2_COMPLETE_RECORD_POLICY_ID,
        expected_raw_sha256=hashlib.sha256(payload).hexdigest(),
        expected_raw_size_bytes=len(payload),
        expected_raw_line_count=len(payload.splitlines()),
        expected_physical_record_starts=physical_starts,
        expected_complete_record_count=complete_records,
        expected_incomplete_record_count=1,
        expected_eof_foot_speed_count=4,
        expected_prefix_sha256=(
            hashlib.sha256(payload[:prefix_end]).hexdigest()
            if prefix_end is not None else None
        ),
        expected_prefix_end_exclusive=prefix_end,
        expected_last_complete_timestamp_ns=last_complete_timestamp_ns,
    )


def test_stream_projection_ignores_unknown_values_and_exposes_only_contract(tmp_path: Path) -> None:
    source = tmp_path / "by2.txt"
    source.write_text(
        "stamp:\n  sec: 10\n  nanosec: 20\n"
        "imu_state:\n  quaternion:\n  - THIS_VALUE_MUST_REMAIN_UNTOUCHED\n"
        "  gyroscope: [0.1, 0.2, 0.3]\n"
        "  accelerometer:\n  - 1\n  - 2\n  - 3\n"
        "  rpy: [ANOTHER_UNPARSEABLE_SENTINEL]\n"
        "position:\n- NOT_A_NUMBER\nvelocity: INVALID_SENTINEL\n"
        "yaw_speed: INVALID_SENTINEL\n"
        "foot_force: [1, 2, 3, 4]\n"
        "foot_position_body: [0.3, -0.2, -0.3, 0.3, 0.2, -0.3, "
        "-0.3, -0.2, -0.3, -0.3, 0.2, -0.3]\n"
        "foot_speed_body:\n- 0\n- 1\n- 2\n- 3\n- 4\n- 5\n"
        "- 6\n- 7\n- 8\n- 9\n- 10\n- 11\n"
        "gait_type: 2\nmode: 1\n---\n",
        encoding="utf-8",
    )
    rows = tuple(h0.iter_hartley_input_projection(source))
    assert len(rows) == 1
    row = rows[0]
    assert row.timestamp_seconds == pytest.approx(10.00000002)
    assert row.gyroscope == (0.1, 0.2, 0.3)
    assert row.accelerometer == (1.0, 2.0, 3.0)
    assert row.foot_force == (1.0, 2.0, 3.0, 4.0)
    assert np.asarray(row.foot_position_body).shape == (4, 3)
    assert np.asarray(row.foot_speed_body).shape == (4, 3)
    assert set(row.__dict__) == {
        "sec", "nanosec", "gyroscope", "accelerometer", "foot_force",
        "foot_position_body", "foot_speed_body", "gait_type", "mode",
    }


@pytest.mark.parametrize(
    "content,expected",
    [
        (
            "stamp:\n  sec: 1\n  nanosec: 2\nimu_state:\n  gyroscope: [1,2]\n"
            "  accelerometer: [1,2,3]\nfoot_force: [1,2,3,4]\n"
            "foot_position_body: [0,0,0,0,0,0,0,0,0,0,0,0]\n"
            "foot_speed_body: [0,0,0,0,0,0,0,0,0,0,0,0]\ngait_type: 1\n---\n",
            "imu_state.gyroscope[2!=3]",
        ),
        (
            "stamp:\n  sec: 1\n  nanosec: 2\nimu_state:\n  gyroscope: [1,2,3]\n"
            "  accelerometer: [1,2,3]\nfoot_force: [1,2,3]\n"
            "foot_position_body: [0,0,0,0,0,0,0,0,0,0,0,0]\n"
            "foot_speed_body: [0,0,0,0,0,0,0,0,0,0,0,0]\ngait_type: 1\n---\n",
            "foot_force[3!=4]",
        ),
        (
            "stamp:\n  sec: 1\n  nanosec: 2\nimu_state:\n  gyroscope: [1,2,3]\n"
            "  accelerometer: [1,2,3]\nfoot_force: [1,2,3,4]\n"
            "foot_position_body: [0,0,0,0,0,0,0,0,0,0,0,0]\n"
            "foot_speed_body: [0,0,0,0,0,0,0,0,0,0,0,0]\n---\n",
            "gait_type",
        ),
    ],
)
def test_projection_fails_closed_on_missing_or_wrong_shape(
    tmp_path: Path, content: str, expected: str
) -> None:
    source = tmp_path / "bad.txt"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(h0.RequiredFieldError, match=re.escape(expected)):
        tuple(h0.iter_hartley_input_projection(source))


def test_complete_record_policy_accepts_only_complete_prefix_and_preserves_raw(
    tmp_path: Path,
) -> None:
    complete = b"".join(_physical_record_bytes(index) for index in range(3))
    payload = complete + _physical_record_bytes(3, foot_speed_count=4, delimiter=False)
    source = tmp_path / "by2.txt"
    source.write_bytes(payload)
    before = source.read_bytes()
    policy = _fixture_policy(
        payload,
        physical_starts=4,
        complete_records=3,
        prefix_end=len(complete),
        last_complete_timestamp_ns=102_000_000_002,
    )
    scan = h0.scan_hartley_complete_record_prefix(source, policy=policy)
    assert len(scan.records) == 3
    assert scan.physical_record_start_count == 4
    assert scan.incomplete_record_count == 1
    assert scan.prefix_end_exclusive == len(complete)
    assert scan.prefix_sha256 == hashlib.sha256(complete).hexdigest()
    assert scan.last_complete_timestamp_ns == 102_000_000_002
    assert scan.physical_records[-1].field_counts["foot_speed_body"] == 4
    assert scan.physical_records[-1].start_byte == len(complete)
    assert source.read_bytes() == before
    assert scan.raw_before_after_identity_match is True
    ledger = h0.trailing_record_ledger(scan)
    manifest = h0.complete_record_prefix_manifest(scan)
    assert manifest["raw_source_path_alias"] == f"<RAW_ROOT>/{h0.BY2_RELATIVE_PATH}"
    assert manifest["raw_source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["raw_source_size"] == len(payload)
    assert manifest["raw_source_line_count"] == len(payload.splitlines())
    assert manifest["data_identity"] == "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
    assert manifest["data_status"] == "REAL_BY2_COMPLETE_RECORD_PREFIX"
    assert manifest["raw_source_complete"] is False
    assert manifest["complete_record_prefix_filter_eligible"] is True
    assert manifest["first_complete_timestamp"] == {
        "sec": 100, "nanosec": 0, "ns": 100_000_000_000,
    }
    assert manifest["last_complete_timestamp"] == {
        "sec": 102, "nanosec": 2, "ns": 102_000_000_002,
    }
    assert manifest["complete_prefix_end_byte_offset"] == len(complete)
    assert manifest["complete_prefix_sha256"] == hashlib.sha256(complete).hexdigest()
    assert manifest["no_imputation"] is True
    assert manifest["no_interpolation"] is True
    assert manifest["raw_source_mutated"] is False
    assert ledger["partial_record_contributes_projection_row"] is False
    assert ledger["foot_speed_role"] == "DIAGNOSTIC_ONLY"
    assert ledger["trailing_incomplete_record_count"] == 1
    assert ledger["trailing_record_used_online"] is False
    assert ledger["exact_missing_fields"] == ["foot_speed_body[4:12]"]
    assert ledger["exact_missing_field_values"]["foot_speed_body"] == {
        "present_count": 4,
        "expected_count": 12,
        "missing_count": 8,
        "missing_indices": list(range(4, 12)),
    }
    with pytest.raises(h0.RequiredFieldError, match="foot_speed_body"):
        tuple(h0.iter_hartley_input_projection(source))


def test_complete_record_policy_counts_crlf_separator_inside_prefix(tmp_path: Path) -> None:
    complete = _physical_record_bytes(0, newline=b"\r\n")
    tail = _physical_record_bytes(
        1, foot_speed_count=4, delimiter=False, newline=b"\r\n"
    )
    payload = complete + tail
    source = tmp_path / "by2-crlf.txt"
    source.write_bytes(payload)
    scan = h0.scan_hartley_complete_record_prefix(
        source,
        policy=_fixture_policy(
            payload,
            physical_starts=2,
            complete_records=1,
            prefix_end=len(complete),
            last_complete_timestamp_ns=100_000_000_000,
        ),
    )
    assert payload[scan.prefix_end_exclusive - 5 : scan.prefix_end_exclusive] == b"---\r\n"
    assert scan.raw_crlf_count == len(payload.splitlines())
    assert scan.raw_bare_lf_count == 0
    assert scan.physical_records[-1].start_line == len(complete.splitlines()) + 1


def test_complete_record_policy_rejects_interior_incomplete_record(tmp_path: Path) -> None:
    payload = (
        _physical_record_bytes(0)
        + _physical_record_bytes(1, foot_speed_count=4)
        + _physical_record_bytes(2)
    )
    source = tmp_path / "interior.txt"
    source.write_bytes(payload)
    with pytest.raises(h0.RequiredFieldError, match="interior/delimited"):
        h0.scan_hartley_complete_record_prefix(
            source,
            policy=_fixture_policy(payload, physical_starts=3, complete_records=2),
        )


def test_complete_record_policy_rejects_two_incomplete_records(tmp_path: Path) -> None:
    payload = (
        _physical_record_bytes(0)
        + _physical_record_bytes(1, foot_speed_count=4, delimiter=False)
        + _physical_record_bytes(2, foot_speed_count=4, delimiter=False)
    )
    source = tmp_path / "two-incomplete.txt"
    source.write_bytes(payload)
    with pytest.raises(h0.RequiredFieldError, match="exactly 1 incomplete.*found 2"):
        h0.scan_hartley_complete_record_prefix(
            source,
            policy=_fixture_policy(payload, physical_starts=3, complete_records=1),
        )


@pytest.mark.parametrize(
    "tail,match",
    [
        (
            _physical_record_bytes(
                1, foot_speed_count=4, omit_field="foot_force", delimiter=False
            ),
            "sole authorized foot_speed",
        ),
        (
            _physical_record_bytes(1, foot_speed_count=5, delimiter=False),
            "sole authorized foot_speed",
        ),
    ],
)
def test_complete_record_policy_rejects_unapproved_terminal_defect(
    tmp_path: Path, tail: bytes, match: str
) -> None:
    payload = _physical_record_bytes(0) + tail
    source = tmp_path / "bad-tail.txt"
    source.write_bytes(payload)
    with pytest.raises(h0.RequiredFieldError, match=match):
        h0.scan_hartley_complete_record_prefix(
            source,
            policy=_fixture_policy(payload, physical_starts=2, complete_records=1),
        )


def test_timing_recomputed_and_nonmonotonic_rejected() -> None:
    records = tuple(_record(index) for index in range(5))
    report = h0.timing_audit(records)
    assert report["message_count"] == 5
    assert report["duration_seconds"] == pytest.approx(0.04)
    assert report["median_rate_hz"] == pytest.approx(100.0)
    with pytest.raises(h0.RequiredFieldError, match="not strictly monotonic"):
        h0.timing_audit((records[0], records[2], records[1]))


def test_native_canonical_foot_mapping_round_trip() -> None:
    native = np.arange(12).reshape(4, 3)
    canonical = h0.native_to_canonical_foot_order(native)
    assert canonical[:, 0].tolist() == [3, 0, 9, 6]
    assert np.array_equal(h0.canonical_to_native_foot_order(canonical), native)
    labels = h0.native_to_canonical_foot_order(np.asarray(h0.NATIVE_FOOT_ORDER))
    assert labels.tolist() == list(h0.CANONICAL_FOOT_ORDER)


def test_frame_candidates_are_proper_round_trip_and_cancel_stationary_gravity() -> None:
    candidates = h0.installation_rotation_candidates()
    active = candidates["SENSOR_TO_BODY_ACTIVE_RZRYRX"]
    inverse = candidates["BODY_TO_SENSOR_ACTIVE_RZRYRX_INVERTED"]
    reporting_gauge = h0.hartley_world_up_gauge_to_reporting_down_gauge()
    for matrix in (*candidates.values(), reporting_gauge):
        check = h0.validate_rotation_matrix(matrix)
        assert check["passed"]
        assert check["determinant"] == pytest.approx(1.0)
        value = np.array([0.2, -0.3, 0.4])
        assert np.allclose(matrix.T @ (matrix @ value), value, atol=1e-14)
    assert (active @ np.array([0.0, 1.0, 0.0]))[2] < 0.0
    assert (inverse @ np.array([0.0, 1.0, 0.0]))[2] > 0.0
    sensor_specific_force = active.T @ np.array([0.0, 0.0, 9.81])
    cancellation = h0.stationary_gravity_cancellation(
        np.tile(sensor_specific_force, (50, 1)), active
    )
    assert cancellation["stationary_specific_force_error_mps2"] < 1.0e-12
    assert cancellation["propagation_gravity_cancellation_norm_mps2"] < 1.0e-12
    assert np.array_equal(reporting_gauge @ [1.0, 2.0, 3.0], [1.0, -2.0, -3.0])
    assert "not an observed north" in (
        h0.hartley_world_up_gauge_to_reporting_down_gauge.__doc__ or ""
    )


def test_contact_proposal_and_hysteresis_are_deterministic_and_force_only() -> None:
    first = _contact_records(speed_relationship="supportive")
    second = _contact_records(speed_relationship="contradictory")
    config_a, proposal_a = h0.derive_force_contact_proposal(first)
    config_b, proposal_b = h0.derive_force_contact_proposal(second)
    assert config_a is not None and config_b is not None
    assert config_a == config_b
    assert proposal_a == proposal_b
    arrays_a = h0._record_arrays(first)
    arrays_b = h0._record_arrays(second)
    states_a, events_a = h0.force_hysteresis_contacts(
        arrays_a["time"], arrays_a["foot_force"], config_a
    )
    states_b, events_b = h0.force_hysteresis_contacts(
        arrays_b["time"], arrays_b["foot_force"], config_b
    )
    assert np.array_equal(states_a, states_b)
    assert events_a == events_b
    assert len(events_a) > 0
    assert proposal_a["decision_signal"] == "foot_force_only"
    assert proposal_a["slip_rejection_enabled"] is False


def test_contact_stability_criteria_pass_per_leg_on_supported_dynamic_input() -> None:
    audit = h0.build_hartley_input_audit(
        _contact_records(), expected_complete_record_count=240
    )
    assert audit["summary"]["contact_input_identifiable"] is True
    assert audit["summary"]["contact_input_stable"] is True
    for leg in h0.NATIVE_FOOT_ORDER:
        result = audit["contact_report"]["per_leg"][leg]
        assert result["contact_input_stable"] is True
        assert result["on_transition_count"] >= 1
        assert result["off_transition_count"] >= 1
        assert result["transition_count"] >= 2
        assert all(result["stability_criteria"].values())


def test_bimodal_but_temporally_static_force_is_not_stable() -> None:
    records = []
    for index in range(240):
        high = index >= 120
        force = (100.0, 105.0, 110.0, 115.0) if high else (2.0, 3.0, 4.0, 5.0)
        speed = (1.0, 1.0, 1.0, 1.0) if high else (10.0, 10.0, 10.0, 10.0)
        records.append(_record(index, force=force, speed_by_leg=speed))
    audit = h0.build_hartley_input_audit(
        tuple(records), expected_complete_record_count=240
    )
    assert audit["summary"]["contact_input_identifiable"] is True
    assert audit["summary"]["contact_input_stable"] is False
    assert all(
        row["transition_count"] == 1
        and row["stability_criteria"]["at_least_one_off_transition"] is False
        for row in audit["contact_report"]["per_leg"].values()
    )
    blocker = h0.hartley_audit_prepublication_blocker(audit)
    assert blocker is not None
    assert blocker["terminal_status"] == "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE"


def test_speed_contradiction_is_diagnostic_and_changes_no_contact_gate() -> None:
    supportive = h0.build_hartley_input_audit(
        _contact_records(speed_relationship="supportive"),
        expected_complete_record_count=240,
    )
    contradictory = h0.build_hartley_input_audit(
        _contact_records(speed_relationship="contradictory"),
        expected_complete_record_count=240,
    )
    assert supportive["transition_rows"] == contradictory["transition_rows"]
    assert supportive["contact_threshold_proposal"] == contradictory["contact_threshold_proposal"]
    assert supportive["summary"]["contact_input_stable"] is True
    assert contradictory["summary"]["contact_input_stable"] is True
    for leg in h0.NATIVE_FOOT_ORDER:
        detail = contradictory["contact_report"]["per_leg"][leg]
        assert detail["diagnostic_no_contact_median_speed_greater_than_contact"] is False
        assert "diagnostic_no_contact_median_speed_greater_than_contact" not in detail[
            "stability_criteria"
        ]
    assert contradictory["contact_report"][
        "foot_speed_changes_threshold_or_state_classification"
    ] is False
    assert contradictory["contact_report"]["foot_speed_role"] == "DIAGNOSTIC_ONLY"
    assert contradictory["contact_report"]["foot_speed_online_allowed"] is False


def test_collapsed_force_distribution_is_explicitly_not_identifiable() -> None:
    records = tuple(_record(index, force=(7.0, 7.0, 7.0, 7.0)) for index in range(20))
    detector, proposal = h0.derive_force_contact_proposal(records)
    assert detector is None
    assert proposal["status"] == "INPUT_NOT_IDENTIFIABLE"
    assert all(not row["identifiable"] for row in proposal["per_leg"].values())


def test_fk_proxy_covariance_residual_count_winsor_psd_and_determinism() -> None:
    records = tuple(
        _record(index, force=(100.0, 100.0, 100.0, 100.0))
        for index in range(180)
    )
    rows_a, report_a = h0.compute_fk_proxy_covariance(records)
    rows_b, report_b = h0.compute_fk_proxy_covariance(records)
    assert rows_a == rows_b
    assert report_a == report_b
    assert report_a["fallback_applied"] is True
    assert report_a["fallback_triggering_legs"] == list(h0.NATIVE_FOOT_ORDER)
    assert report_a["status"] == "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE"
    assert report_a["filter_eligible"] is True
    assert report_a["floor_dominates_all_raw_leg_covariances"] is True
    assert report_a["foot_speed_role"] == "DIAGNOSTIC_ONLY"
    assert report_a["foot_speed_online_allowed"] is False
    assert report_a["foot_speed_changes_contact_threshold_or_state"] is False
    assert report_a["winsor_method"] == "linear"
    for leg in h0.NATIVE_FOOT_ORDER:
        detail = report_a["per_leg"][leg]
        assert detail["residual_count"] == 179
        assert detail["eligibility_counts"]["eligible"] == 179
        assert detail["well_conditioned"] is False
        matrix = np.asarray(detail["final_covariance_m2"])
        assert np.allclose(matrix, matrix.T, atol=1e-15)
        assert np.min(np.linalg.eigvalsh(matrix)) >= 1.0e-8 - 1.0e-18
        assert detail["raw_symmetric_condition_2norm"] is None
        assert detail["final_condition_2norm"] <= 1.0e8
        assert np.all(
            np.asarray(detail["winsor_quantile_0p5_m"])
            <= np.asarray(detail["winsor_quantile_99p5_m"])
        )


def test_fk_proxy_covariance_endpoint_gates_remove_both_adjacent_pairs() -> None:
    records = list(
        _record(index, force=(100.0, 100.0, 100.0, 100.0))
        for index in range(180)
    )
    middle = records[90]
    records[90] = h0.HartleyInputRecord(
        **{**middle.__dict__, "gyroscope": (0.051, 0.0, 0.0)}
    )
    _rows, report = h0.compute_fk_proxy_covariance(tuple(records))
    for leg in h0.NATIVE_FOOT_ORDER:
        assert report["per_leg"][leg]["residual_count"] == 177


def test_fk_proxy_covariance_accel_endpoint_is_inclusive() -> None:
    records = []
    for index in range(180):
        row = _record(index, force=(100.0, 100.0, 100.0, 100.0))
        records.append(h0.HartleyInputRecord(
            **{**row.__dict__, "accelerometer": (0.0, 0.0, 10.31)}
        ))
    _rows, report = h0.compute_fk_proxy_covariance(tuple(records))
    assert report["eligibility"][
        "absolute_accel_norm_minus_9p81_at_most_mps2"
    ] == 0.5
    for leg in h0.NATIVE_FOOT_ORDER:
        assert report["per_leg"][leg]["residual_count"] == 179


def test_fk_proxy_covariance_matches_frozen_residual_and_linear_winsor_math() -> None:
    records = list(
        _record(index, force=(100.0, 100.0, 100.0, 100.0))
        for index in range(180)
    )
    last = records[-1]
    shifted_positions = tuple(
        (position[0] + 1.0, position[1], position[2])
        for position in last.foot_position_body
    )
    records[-1] = h0.HartleyInputRecord(
        **{**last.__dict__, "foot_position_body": shifted_positions}
    )
    _rows, report = h0.compute_fk_proxy_covariance(tuple(records))
    residuals = []
    for index in range(1, len(records)):
        dt = records[index].timestamp_seconds - records[index - 1].timestamp_seconds
        p0 = np.asarray(records[index - 1].foot_position_body[0])
        p1 = np.asarray(records[index].foot_position_body[0])
        v0 = np.asarray(records[index - 1].foot_speed_body[0])
        v1 = np.asarray(records[index].foot_speed_body[0])
        residuals.append(p1 - p0 - 0.5 * (v0 + v1) * dt)
    residual_array = np.asarray(residuals)
    center = np.median(residual_array, axis=0)
    lower = np.percentile(residual_array, 0.5, axis=0, method="linear")
    upper = np.percentile(residual_array, 99.5, axis=0, method="linear")
    winsorized = np.clip(residual_array, lower, upper)
    expected = (winsorized - center).T @ (winsorized - center) / (
        len(winsorized) - 1
    )
    detail = report["per_leg"]["FR"]
    assert detail["component_center_m"] == pytest.approx(center.tolist())
    assert detail["winsor_quantile_0p5_m"] == pytest.approx(lower.tolist())
    assert detail["winsor_quantile_99p5_m"] == pytest.approx(upper.tolist())
    assert np.asarray(detail["raw_covariance_m2"]) == pytest.approx(expected)
    assert upper[0] < residual_array[-1, 0]


def test_fk_proxy_covariance_fallback_is_shared_and_records_triggering_legs() -> None:
    records = tuple(
        _record(index, force=(100.0, 100.0, 100.0, 100.0))
        for index in range(50)
    )
    _rows, report = h0.compute_fk_proxy_covariance(records)
    assert report["fallback_applied"] is True
    assert report["fallback_triggering_legs"] == list(h0.NATIVE_FOOT_ORDER)
    selected = [
        report["per_leg"][leg]["selected_covariance_m2"]
        for leg in h0.NATIVE_FOOT_ORDER
    ]
    assert selected[1:] == [selected[0], selected[0], selected[0]]
    fallback = np.asarray(report["fallback_covariance_m2"])
    assert np.allclose(fallback, fallback.T, atol=1e-15)
    assert np.min(np.linalg.eigvalsh(fallback)) >= 1.0e-8 - 1.0e-18


def test_full_synthetic_audit_and_no_replace_machine_outputs(tmp_path: Path) -> None:
    records = _contact_records()
    audit = h0.build_hartley_input_audit(
        records, expected_complete_record_count=len(records)
    )
    summary = h0.write_hartley_input_audit(tmp_path / "audit", audit)
    assert summary["complete_record_count_matches_policy"]
    assert summary["expected_complete_record_count"] == len(records)
    assert "expected_message_count" not in summary
    assert "message_count_matches_expected" not in summary
    assert summary["foot_speed_role"] == "DIAGNOSTIC_ONLY"
    assert summary["filter_run_count"] == 0
    assert summary["filter_run_executed"] is False
    expected = {
        "BY2_PROJECTION_AUDIT_SUMMARY.json", "FK_PROXY_AUDIT.csv",
        "FK_PROXY_AUDIT.json", "CONTACT_FORCE_DISTRIBUTIONS.csv",
        "CONTACT_SPEED_DISTRIBUTIONS.csv", "CONTACT_TRANSITION_AUDIT.csv",
        "CONTACT_THRESHOLD_PROPOSAL.yaml", "CONTACT_INPUT_AUDIT.json",
        "BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json",
        "BY2_TRAILING_RECORD_LEDGER.json",
        "FK_PROXY_COVARIANCE_ESTIMATION.csv",
        "FK_PROXY_COVARIANCE_SUMMARY.json",
    }
    assert {path.name for path in (tmp_path / "audit").iterdir()} == expected
    threshold = yaml.safe_load(
        (tmp_path / "audit/CONTACT_THRESHOLD_PROPOSAL.yaml").read_text(encoding="utf-8")
    )
    assert threshold["reference_tuned"] is False
    with pytest.raises(FileExistsError):
        h0.write_hartley_input_audit(tmp_path / "audit", audit)


def test_all_prepublication_gates_block_before_canonical_output(tmp_path: Path) -> None:
    base = h0.build_hartley_input_audit(
        _contact_records(), expected_complete_record_count=240
    )
    assert h0.hartley_audit_prepublication_blocker(base) is None
    cases = []
    wrong_count = copy.deepcopy(base)
    wrong_count["summary"]["complete_record_count_matches_policy"] = False
    cases.append((wrong_count, "BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING"))
    unidentified = copy.deepcopy(base)
    unidentified["summary"]["contact_input_identifiable"] = False
    cases.append((unidentified, "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE"))
    unstable = copy.deepcopy(base)
    unstable["summary"]["contact_input_stable"] = False
    cases.append((unstable, "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE"))
    bad_geometry = copy.deepcopy(base)
    bad_geometry["fk_report"]["native_flu_geometry_sanity_pass"] = False
    cases.append((bad_geometry, "BLOCKED_LSE01_FOOT_ORDER_CONTRACT_UNRESOLVED"))
    bad_covariance = copy.deepcopy(base)
    bad_covariance["fk_covariance_report"]["filter_eligible"] = False
    cases.append((bad_covariance, "BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING"))
    for index, (audit, expected_status) in enumerate(cases):
        blocker = h0.hartley_audit_prepublication_blocker(audit)
        assert blocker is not None
        assert blocker["terminal_status"] == expected_status
        destination = tmp_path / f"blocked-{index}"
        with pytest.raises(h0.HartleyH0H2Error, match=expected_status):
            h0.write_hartley_input_audit(destination, audit)
        assert not destination.exists()


def test_cli_checks_stability_before_calling_transactional_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts/paper_rebuild/audit_hartley_h0_h2_by2.py"
    )
    spec = importlib.util.spec_from_file_location("hartley_h0_h2_cli_test", script)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    blocked_audit = h0.build_hartley_input_audit(
        _contact_records(), expected_complete_record_count=240
    )
    blocked_audit["summary"]["contact_input_stable"] = False
    destination = tmp_path / "canonical-output"
    paths = SimpleNamespace(by2_source=tmp_path / "unused", default_output_root=destination)
    monkeypatch.setattr(cli, "resolve_hartley_audit_paths", lambda _path: paths)
    monkeypatch.setattr(cli, "verify_by2_hash_lock", lambda _paths: {})
    monkeypatch.setattr(
        cli,
        "scan_hartley_complete_record_prefix",
        lambda *_args, **_kwargs: SimpleNamespace(
            records=(),
            raw_before_after_identity_match=True,
            policy=SimpleNamespace(policy_id=h0.BY2_COMPLETE_RECORD_POLICY_ID),
            complete_record_count=h0.EXPECTED_BY2_USABLE_RECORD_COUNT,
        ),
    )
    monkeypatch.setattr(cli, "build_hartley_input_audit", lambda *_args, **_kwargs: blocked_audit)

    def publication_must_not_run(*_args: object, **_kwargs: object) -> None:
        pytest.fail("transactional writer was called before the stability gate")

    monkeypatch.setattr(cli, "write_hartley_input_audit", publication_must_not_run)
    assert cli.main(["--paths-config", str(tmp_path / "unused.yaml")]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["terminal_status"] == "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE"
    assert payload["canonical_output_written"] is False
    assert not destination.exists()


def test_transaction_failure_removes_only_owned_temp_and_leaves_final_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = h0.build_hartley_input_audit(
        _contact_records(), expected_complete_record_count=240
    )
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()

    def fail_validation(_root: Path) -> None:
        raise h0.HartleyH0H2Error("injected transaction validation failure")

    monkeypatch.setattr(h0, "_validate_audit_transaction", fail_validation)
    destination = tmp_path / "audit"
    with pytest.raises(h0.HartleyH0H2Error, match="injected"):
        h0.write_hartley_input_audit(destination, audit)
    assert not destination.exists()
    assert unrelated.is_dir()
    assert not list(tmp_path.glob(".audit.hartley-audit-tmp-*"))


def _canonical_hash_lock_fixture(
    tmp_path: Path,
    *,
    canonical_row_count: int = 1,
) -> tuple[h0.HartleyAuditPaths, Path, str]:
    raw = tmp_path / "raw"
    clean = tmp_path / "clean"
    source = raw / h0.BY2_RELATIVE_PATH
    source.parent.mkdir(parents=True)
    source.write_text("projected-source\n", encoding="utf-8")
    lock = clean / "01_RAW_HASH_LOCK/BY2_HASH_LOCK.csv"
    lock.parent.mkdir(parents=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with lock.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=h0.BY2_HASH_LOCK_COLUMNS)
        writer.writeheader()
        for _index in range(canonical_row_count):
            writer.writerow({
                "relative_path": h0.BY2_RELATIVE_PATH,
                "size_bytes": source.stat().st_size,
                "sha256": digest,
                "line_count_or_file_type": "line_count:1",
                "role": "GO2_BODY_HIGH_LEVEL_SOURCE_NOT_TRUTH",
                "dataset": "BY2",
                "immutable": "true",
                "mtime_ns": "1",
            })
    config = tmp_path / "DATA_PATHS.CLEAN3R4.local.yaml"
    config.write_text(yaml.safe_dump({
        "schema_version": "paper_rebuild.paths.v1",
        "paths": {
            "raw_root": str(raw),
            "clean_root": str(clean),
            "by2_go2_body": str(source),
        },
    }), encoding="utf-8")
    return h0.resolve_hartley_audit_paths(config), lock, digest


def test_canonical_source_resolves_only_from_trusted_hash_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, lock, digest = _canonical_hash_lock_fixture(tmp_path)
    monkeypatch.setattr(h0, "TRUSTED_BY2_HASH_LOCK_SHA256", h0.sha256_file(lock))
    assert paths.by2_source == (paths.raw_root / h0.BY2_RELATIVE_PATH).resolve()
    identity = h0.verify_by2_hash_lock(paths)
    assert identity["relative_path"] == h0.BY2_RELATIVE_PATH
    assert identity["sha256"] == digest
    assert identity["locked_line_count"] == 1
    assert identity["hash_lock_trusted_identity_verified"] is True


def test_wrong_hash_lock_identity_fails_before_row_use(tmp_path: Path) -> None:
    paths, _lock, _digest = _canonical_hash_lock_fixture(tmp_path)
    with pytest.raises(h0.HartleyH0H2Error, match="trusted identity"):
        h0.verify_by2_hash_lock(paths)


def test_duplicate_canonical_hash_lock_row_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, lock, _digest = _canonical_hash_lock_fixture(
        tmp_path, canonical_row_count=2
    )
    monkeypatch.setattr(h0, "TRUSTED_BY2_HASH_LOCK_SHA256", h0.sha256_file(lock))
    with pytest.raises(h0.HartleyH0H2Error, match="duplicated"):
        h0.verify_by2_hash_lock(paths)


def test_scoped_implementation_has_no_external_reference_or_broad_parser_dependency() -> None:
    module_text = Path(h0.__file__).read_text(encoding="utf-8").lower()
    script_text = (
        Path(__file__).resolve().parents[2]
        / "scripts/paper_rebuild/audit_hartley_h0_h2_by2.py"
    ).read_text(encoding="utf-8").lower()
    combined = module_text + script_text
    assert "trace" not in combined
    assert "go2_body_state_parser" not in combined
    assert "by2_algorithm_runner" not in combined
    for token in ("quaternion", "yaw_speed", "final_v23", "legsa_output"):
        assert token not in combined
