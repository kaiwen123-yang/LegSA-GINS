"""Authenticated Go2 prefix to official GINav format-2 IMU increments."""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import math
import os
import statistics
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .constants import (
    GO2_COMPLETE_RECORDS,
    GO2_IMU_IDENTITY,
    GO2_INCREMENT_POLICY_SOURCE,
    GO2_INVALID_DT_POLICY,
    GO2_PREFIX_BYTES,
    GO2_PREFIX_SHA256,
    GO2_RAW_SHA256,
    GO2_RAW_SIZE_BYTES,
    GO2_SAMPLE_RATE_HZ,
    GO2_SAMPLE_RATE_SOURCE,
)
from .source import AccessLedger, sha256_file
from .time_contract import NANOSECONDS, WEEK_SECONDS, utc_unix_ns_to_gps


class ImuAdapterError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class Go2ImuRecord:
    timestamp_ns: int
    gyro_flu_radps: tuple[float, float, float]
    accelerometer_flu_mps2: tuple[float, float, float]


@dataclasses.dataclass(frozen=True)
class GinavImuIncrement:
    gps_week: int
    gps_sow_nanoseconds: int
    delta_angle_rfu_rad: tuple[float, float, float]
    delta_velocity_rfu_mps: tuple[float, float, float]
    dt_nanoseconds: int


def _format_sow_nanoseconds(value: int) -> str:
    whole, fractional = divmod(value, NANOSECONDS)
    return f"{whole}.{fractional:09d}"


def flu_to_rfu(vector: Sequence[float]) -> tuple[float, float, float]:
    if len(vector) != 3:
        raise ImuAdapterError("FLU vector must have three components")
    forward, left, up = (float(item) for item in vector)
    if not all(math.isfinite(item) for item in (forward, left, up)):
        raise ImuAdapterError("FLU vector contains nonfinite values")
    return -left, forward, up


def rfu_to_flu(vector: Sequence[float]) -> tuple[float, float, float]:
    if len(vector) != 3:
        raise ImuAdapterError("RFU vector must have three components")
    right, forward, up = (float(item) for item in vector)
    return forward, -right, up


def _parse_finite(text: str, role: str) -> float:
    try:
        value = float(text.strip().strip("'\""))
    except ValueError as exc:
        raise ImuAdapterError(f"invalid Go2 {role}") from exc
    if not math.isfinite(value):
        raise ImuAdapterError(f"nonfinite Go2 {role}")
    return value


def _prefix_lines(path: Path, byte_count: int) -> Iterator[bytes]:
    remaining = byte_count
    with path.open("rb") as handle:
        while remaining:
            line = handle.readline(remaining)
            if not line:
                raise ImuAdapterError("Go2 source is shorter than authenticated prefix")
            remaining -= len(line)
            yield line
    if not line.endswith((b"\n", b"\r")):
        raise ImuAdapterError("authenticated Go2 prefix does not end at a line boundary")


def iter_authenticated_go2_imu_records(path: str | Path) -> Iterator[Go2ImuRecord]:
    """Materialize only stamp, gyro, and accelerometer from complete records."""

    source = Path(path)
    sec: int | None = None
    nanosec: int | None = None
    gyro: list[float] = []
    accel: list[float] = []
    top = ""
    array = ""
    array_indent = -1

    def finish() -> Go2ImuRecord | None:
        if sec is None and nanosec is None and not gyro and not accel:
            return None
        if sec is None or nanosec is None or len(gyro) != 3 or len(accel) != 3:
            raise ImuAdapterError("complete-prefix Go2 IMU projection is incomplete")
        if not 0 <= nanosec < NANOSECONDS:
            raise ImuAdapterError("Go2 stamp.nanosec is out of range")
        return Go2ImuRecord(
            sec * NANOSECONDS + nanosec,
            tuple(gyro), tuple(accel),
        )

    for raw in _prefix_lines(source, GO2_PREFIX_BYTES):
        try:
            line = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ImuAdapterError("Go2 authenticated prefix is not UTF-8") from exc
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if stripped == "---":
            item = finish()
            if item is not None:
                yield item
            sec = nanosec = None
            gyro = []
            accel = []
            top = array = ""
            array_indent = -1
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if indent == 0 and stripped.endswith(":"):
            top = stripped[:-1]
            array = ""
            array_indent = -1
            continue
        if top == "stamp" and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            value = _parse_finite(raw_value, f"stamp.{key}")
            if value != int(value):
                raise ImuAdapterError(f"Go2 stamp.{key} is not integral")
            if key == "sec":
                sec = int(value)
            elif key == "nanosec":
                nanosec = int(value)
            continue
        if top != "imu_state":
            # Serialized forbidden fields are skipped lexically and never
            # parsed, retained, transformed, or exposed to navigation.
            continue
        if stripped in {"gyroscope:", "accelerometer:"}:
            array = stripped[:-1]
            array_indent = indent
            continue
        if array and indent >= array_indent and stripped.startswith("-"):
            target = gyro if array == "gyroscope" else accel
            target.append(_parse_finite(stripped[1:], f"imu_state.{array}"))
            continue
        if array and indent <= array_indent:
            array = ""
            array_indent = -1

    # The authenticated byte boundary includes the final record separator, so
    # any materialized state here means the frozen prefix contract changed.
    if finish() is not None:
        raise ImuAdapterError("authenticated Go2 prefix has an unterminated record")


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ImuAdapterError("cannot summarize an empty dt vector")
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def build_format2_increments(
    records: Sequence[Go2ImuRecord],
) -> tuple[tuple[GinavImuIncrement, ...], dict[str, Any]]:
    if len(records) != GO2_COMPLETE_RECORDS:
        raise ImuAdapterError(
            f"Go2 authenticated record count is {len(records)}, expected {GO2_COMPLETE_RECORDS}"
        )
    increments: list[GinavImuIncrement] = []
    all_dt_ns: list[int] = []
    skipped_lte_zero = 0
    skipped_gt_0p1 = 0
    flu_angle_sums = [0.0, 0.0, 0.0]
    flu_velocity_sums = [0.0, 0.0, 0.0]
    rfu_angle_sums = [0.0, 0.0, 0.0]
    rfu_velocity_sums = [0.0, 0.0, 0.0]

    for previous, current in zip(records, records[1:]):
        dt_ns = current.timestamp_ns - previous.timestamp_ns
        if dt_ns <= 0:
            skipped_lte_zero += 1
            continue
        all_dt_ns.append(dt_ns)
        if dt_ns > 100_000_000:
            skipped_gt_0p1 += 1
            continue
        dt_seconds = dt_ns / NANOSECONDS
        angle_flu = tuple(value * dt_seconds for value in current.gyro_flu_radps)
        velocity_flu = tuple(
            value * dt_seconds for value in current.accelerometer_flu_mps2
        )
        angle_rfu = flu_to_rfu(angle_flu)
        velocity_rfu = flu_to_rfu(velocity_flu)
        if any(not math.isfinite(value) for value in (*angle_rfu, *velocity_rfu)):
            raise ImuAdapterError("Go2 format-2 increment is nonfinite")
        gps = utc_unix_ns_to_gps(current.timestamp_ns)
        increments.append(
            GinavImuIncrement(
                gps.week, gps.sow_nanoseconds, angle_rfu, velocity_rfu, dt_ns
            )
        )
        for index in range(3):
            flu_angle_sums[index] += angle_flu[index]
            flu_velocity_sums[index] += velocity_flu[index]
            rfu_angle_sums[index] += angle_rfu[index]
            rfu_velocity_sums[index] += velocity_rfu[index]

    if not increments:
        raise ImuAdapterError("Go2 prefix yielded no valid format-2 increments")
    if len(increments) != len(records) - 1 - skipped_lte_zero - skipped_gt_0p1:
        raise ImuAdapterError("frozen current-sample interval conservation failed")
    expected_angle_rfu = flu_to_rfu(flu_angle_sums)
    expected_velocity_rfu = flu_to_rfu(flu_velocity_sums)
    max_conservation_error = max(
        abs(expected_angle_rfu[i] - rfu_angle_sums[i])
        for i in range(3)
    )
    max_conservation_error = max(
        max_conservation_error,
        max(abs(expected_velocity_rfu[i] - rfu_velocity_sums[i]) for i in range(3)),
    )
    dt_seconds_values = sorted(value / NANOSECONDS for value in all_dt_ns)
    first_gps = utc_unix_ns_to_gps(records[0].timestamp_ns)
    last_gps = utc_unix_ns_to_gps(records[-1].timestamp_ns)
    output_time_strictly_monotonic = all(
        (
            current.gps_week * WEEK_SECONDS * NANOSECONDS
            + current.gps_sow_nanoseconds
        )
        > (
            previous.gps_week * WEEK_SECONDS * NANOSECONDS
            + previous.gps_sow_nanoseconds
        )
        for previous, current in zip(increments, increments[1:])
    )
    interval_outcome_conservation = (
        len(records) - 1
        == len(increments) + skipped_lte_zero + skipped_gt_0p1
    )
    audit = {
        "schema_version": "ginav2021.go2_imu_adapter_audit.v1",
        "data_identity": GO2_IMU_IDENTITY,
        "input_row_count": len(records),
        "output_row_count": len(increments),
        "first_record_skipped_no_prior_interval": True,
        "invalid_dt_lte_0_skipped_count": skipped_lte_zero,
        "invalid_dt_gt_0p1_skipped_count": skipped_gt_0p1,
        "invalid_dt_total_skipped_count": skipped_lte_zero + skipped_gt_0p1,
        "invalid_dt_policy": GO2_INVALID_DT_POLICY,
        "increment_and_invalid_dt_policy_source": GO2_INCREMENT_POLICY_SOURCE,
        "nonpositive_dt_count": skipped_lte_zero,
        "time_strictly_monotonic": skipped_lte_zero == 0,
        "input_time_strictly_monotonic": skipped_lte_zero == 0,
        "output_time_strictly_monotonic": output_time_strictly_monotonic,
        "candidate_interval_count": len(records) - 1,
        "interval_outcome_conservation_pass": interval_outcome_conservation,
        "dt_seconds": {
            "minimum": dt_seconds_values[0],
            "median": statistics.median(dt_seconds_values),
            "p95": _percentile(dt_seconds_values, 0.95),
            "maximum": dt_seconds_values[-1],
        },
        "source_units": {"gyro": "rad/s", "accelerometer": "m/s^2"},
        "output_units": {"delta_angle": "rad", "delta_velocity": "m/s"},
        "source_frame": "FLU",
        "output_frame": "RFU",
        "frame_map": "[R,F,U]=[-L,F,U]",
        "frame_round_trip_exact_on_test_basis": (
            rfu_to_flu(flu_to_rfu((1.25, -2.5, 3.75))) == (1.25, -2.5, 3.75)
        ),
        "increment_policy": "current_sample_times_dt",
        "data_format": 2,
        "sample_rate_hz": GO2_SAMPLE_RATE_HZ,
        "sample_rate_source": GO2_SAMPLE_RATE_SOURCE,
        "sqrt_dt_preprocessing": False,
        "componentwise_increment_conservation_max_abs": max_conservation_error,
        "finite_input_count": len(records) * 6,
        "finite_output_count": len(increments) * 6,
        "first_utc_unix_ns": records[0].timestamp_ns,
        "last_utc_unix_ns": records[-1].timestamp_ns,
        "first_gps_week": first_gps.week,
        "first_gps_sow_seconds": first_gps.sow_seconds,
        "last_gps_week": last_gps.week,
        "last_gps_sow_seconds": last_gps.sow_seconds,
        "first_output_gps_week": increments[0].gps_week,
        "first_output_gps_sow_seconds": (
            increments[0].gps_sow_nanoseconds / NANOSECONDS
        ),
        "last_output_gps_week": increments[-1].gps_week,
        "last_output_gps_sow_seconds": (
            increments[-1].gps_sow_nanoseconds / NANOSECONDS
        ),
        "quaternion_materialized": False,
        "rpy_materialized": False,
        "position_materialized": False,
        "velocity_materialized": False,
        "yaw_speed_materialized": False,
        "foot_fields_materialized": False,
        "hartley_state_materialized": False,
        "pass": (
            max_conservation_error < 1e-12
            and interval_outcome_conservation
        ),
    }
    if not audit["pass"]:
        raise ImuAdapterError("FLU/RFU increment conservation failed")
    return tuple(increments), audit


def write_ginav_imu_csv(
    destination: str | Path,
    increments: Sequence[GinavImuIncrement],
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            (
                "gps_week", "gps_sow", "delta_angle_r", "delta_angle_f",
                "delta_angle_u", "delta_velocity_r", "delta_velocity_f",
                "delta_velocity_u",
            )
        )
        for row in increments:
            writer.writerow(
                (
                    row.gps_week,
                    _format_sow_nanoseconds(row.gps_sow_nanoseconds),
                    *(f"{value:.17g}" for value in row.delta_angle_rfu_rad),
                    *(f"{value:.17g}" for value in row.delta_velocity_rfu_mps),
                )
            )
    return path


def adapt_go2_imu(
    source_path: str | Path,
    destination_csv: str | Path,
    *,
    ledger: AccessLedger | None = None,
) -> dict[str, Any]:
    source = Path(source_path).resolve(strict=True)
    stat_before = source.stat()
    if stat_before.st_size != GO2_RAW_SIZE_BYTES:
        raise ImuAdapterError("Go2 raw size differs from authenticated identity")
    full_hash = sha256_file(source)
    prefix_hash = sha256_file(source, limit=GO2_PREFIX_BYTES)
    if full_hash != GO2_RAW_SHA256 or prefix_hash != GO2_PREFIX_SHA256:
        raise ImuAdapterError("Go2 raw or complete-prefix hash mismatch")
    if ledger is not None:
        ledger.record(source, role="GO2_BODY_IMU_GYRO_ACCEL_COMPLETE_PREFIX")
    records = tuple(iter_authenticated_go2_imu_records(source))
    increments, audit = build_format2_increments(records)
    output = write_ginav_imu_csv(destination_csv, increments)
    stat_after = source.stat()
    if stat_before.st_size != stat_after.st_size or stat_before.st_mtime_ns != stat_after.st_mtime_ns:
        raise ImuAdapterError("Go2 raw metadata changed during adaptation")
    if sha256_file(source) != full_hash:
        raise ImuAdapterError("Go2 raw bytes changed during adaptation")
    return {
        **audit,
        "source_path": str(source),
        "source_bytes": stat_before.st_size,
        "source_sha256": full_hash,
        "authenticated_prefix_bytes": GO2_PREFIX_BYTES,
        "authenticated_prefix_sha256": prefix_hash,
        "output_path": str(output),
        "output_sha256": sha256_file(output),
        "runtime_only_not_for_commit": True,
        "raw_source_mutated": False,
    }
