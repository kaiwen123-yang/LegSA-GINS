"""Input-only BY2 projection and adaptation audits for Hartley H0--H2.

This module is intentionally not a state estimator.  It streams a strict
projection of the Go2 high-level message, validates the H0--H2 input contract,
and computes deterministic timing, foot-geometry, FK-proxy, and force-contact
statistics.  Unknown message fields are skipped before their values are
parsed.  No navigation propagation, measurement update, or reference-data
reader is present here.
"""

from __future__ import annotations

import csv
import ctypes
import errno
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np
import yaml


BY2_RELATIVE_PATH = "BY2_BY3/2026-03-06/高层数据/by2.txt"
TRUSTED_BY2_HASH_LOCK_SHA256 = (
    "7103880ff53eb195c7d9acdbb87292a7be20e4a58b764da29f848e80a84ecb6c"
)
BY2_HASH_LOCK_COLUMNS = (
    "relative_path",
    "size_bytes",
    "sha256",
    "line_count_or_file_type",
    "role",
    "dataset",
    "immutable",
    "mtime_ns",
)
HARTLEY_INPUT_AUDIT_RELATIVE = (
    "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/"
    "07_LSE01_HARTLEY_CONTACT_INEKF/03_BY2_INPUT_AUDIT"
)
EXPECTED_BY2_MESSAGE_COUNT = 63_278
EXPECTED_BY2_USABLE_RECORD_COUNT = 63_277

BY2_COMPLETE_RECORD_POLICY_ID = "BY2_COMPLETE_RECORD_POLICY_V1"
PRODUCTION_BY2_RAW_SHA256 = (
    "95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278"
)
PRODUCTION_BY2_RAW_SIZE_BYTES = 92_352_512
PRODUCTION_BY2_RAW_LINE_COUNT = 4_682_569
PRODUCTION_BY2_EOF_FOOT_SPEED_COUNT = 4
PRODUCTION_BY2_PREFIX_END_EXCLUSIVE = 92_351_234
PRODUCTION_BY2_PREFIX_SHA256 = (
    "03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097"
)
PRODUCTION_BY2_TAIL_BYTES = 1_278
PRODUCTION_BY2_TAIL_SHA256 = (
    "b9489cc1de96a7115de858e853389b8cf43e5245dcf57dd6b5ce99c573d7a30b"
)
PRODUCTION_BY2_FIRST_COMPLETE_TIMESTAMP_NS = 1_772_784_044_887_078_145
PRODUCTION_BY2_LAST_COMPLETE_TIMESTAMP_NS = 1_772_784_350_085_048_802
PRODUCTION_BY2_DURATION_NS = 305_197_970_657
PRODUCTION_BY2_EOF_TIMESTAMP_NS = 1_772_784_350_091_049_397
PRODUCTION_BY2_FINAL_RECORD_START_LINE = 4_682_505
PRODUCTION_BY2_CRLF_COUNT = 4_682_568
PRODUCTION_BY2_BARE_LF_COUNT = 1

FROZEN_CONTACT_OFF_THRESHOLDS = (24.8, 25.2, 23.4, 24.0)
FROZEN_CONTACT_ON_THRESHOLDS = (34.2, 33.8, 30.6, 32.0)
FROZEN_CONTACT_DWELL_SAMPLES = 3
FROZEN_CONTACT_DWELL_SECONDS = 0.012035608291625977
FK_COVARIANCE_PRIMARY_SCALE = 1.0
FK_COVARIANCE_SENSITIVITY_SCALES = (0.25, 1.0, 4.0)
FK_COVARIANCE_MIN_RESIDUALS = 100
FK_COVARIANCE_EIGENVALUE_FLOOR_M2 = 1.0e-8
FK_COVARIANCE_MAX_CONDITION = 1.0e8
FK_COVARIANCE_MAX_SYMMETRY_ERROR = 1.0e-12

NATIVE_FOOT_ORDER = ("FR", "FL", "RR", "RL")
CANONICAL_FOOT_ORDER = ("FL", "FR", "RL", "RR")
NATIVE_TO_CANONICAL = (1, 0, 3, 2)
CANONICAL_TO_NATIVE = (1, 0, 3, 2)

IMU_INSTALL_RPY_DEG = (-1.0, 0.0, 0.0)
DEFAULT_MINIMUM_DWELL_SAMPLES = 3
DEFAULT_HISTOGRAM_BINS = 32
CONTACT_STABILITY_MIN_STATE_FRACTION = 0.01
NUMERICAL_TOLERANCE = 1.0e-12


class HartleyH0H2Error(ValueError):
    """An H0--H2 source, schema, timing, or audit contract failed closed."""


class RequiredFieldError(HartleyH0H2Error):
    """A projected field was absent, malformed, nonfinite, or mis-shaped."""


class ContactInputNotIdentifiable(HartleyH0H2Error):
    """The input-only force distribution cannot support a stable proposal."""


@dataclass(frozen=True)
class CompleteRecordPolicy:
    """Hash/count/signature lock for one complete-prefix source identity."""

    policy_id: str
    expected_raw_sha256: str
    expected_raw_size_bytes: int
    expected_raw_line_count: int
    expected_physical_record_starts: int
    expected_complete_record_count: int
    expected_incomplete_record_count: int = 1
    expected_eof_foot_speed_count: int = PRODUCTION_BY2_EOF_FOOT_SPEED_COUNT
    expected_prefix_sha256: str | None = None
    expected_prefix_end_exclusive: int | None = None
    expected_first_complete_timestamp_ns: int | None = None
    expected_last_complete_timestamp_ns: int | None = None
    expected_duration_ns: int | None = None
    expected_tail_sha256: str | None = None
    expected_tail_bytes: int | None = None
    expected_final_record_start_line: int | None = None
    expected_eof_timestamp_ns: int | None = None
    expected_crlf_count: int | None = None
    expected_bare_lf_count: int | None = None

    def __post_init__(self) -> None:
        if self.policy_id != BY2_COMPLETE_RECORD_POLICY_ID:
            raise HartleyH0H2Error("unsupported complete-record policy identity")
        if not _LOWER_SHA256.fullmatch(self.expected_raw_sha256):
            raise HartleyH0H2Error("complete-record policy raw SHA256 is malformed")
        if self.expected_prefix_sha256 is not None and not _LOWER_SHA256.fullmatch(
            self.expected_prefix_sha256
        ):
            raise HartleyH0H2Error("complete-record policy prefix SHA256 is malformed")
        if self.expected_tail_sha256 is not None and not _LOWER_SHA256.fullmatch(
            self.expected_tail_sha256
        ):
            raise HartleyH0H2Error("complete-record policy tail SHA256 is malformed")
        integer_values = (
            self.expected_raw_size_bytes,
            self.expected_raw_line_count,
            self.expected_physical_record_starts,
            self.expected_complete_record_count,
            self.expected_incomplete_record_count,
            self.expected_eof_foot_speed_count,
        )
        if any(value < 0 for value in integer_values):
            raise HartleyH0H2Error("complete-record policy counts must be nonnegative")
        if self.expected_complete_record_count < 1:
            raise HartleyH0H2Error("complete-record policy requires a nonempty prefix")
        if self.expected_prefix_end_exclusive is not None and (
            self.expected_prefix_end_exclusive < 0
            or self.expected_prefix_end_exclusive > self.expected_raw_size_bytes
        ):
            raise HartleyH0H2Error("complete-record policy prefix byte boundary is invalid")
        optional_signature = (
            self.expected_tail_sha256,
            self.expected_tail_bytes,
            self.expected_final_record_start_line,
            self.expected_eof_timestamp_ns,
            self.expected_crlf_count,
            self.expected_bare_lf_count,
        )
        if any(value is not None for value in optional_signature) and any(
            value is None for value in optional_signature
        ):
            raise HartleyH0H2Error("complete-record EOF/newline signature must be all-or-none")


@dataclass(frozen=True)
class PhysicalRecordEvidence:
    """Exact source location and projected shape evidence for one physical record."""

    record_index: int
    start_byte: int
    end_byte_exclusive: int
    start_line: int
    end_line: int
    delimiter_line: int | None
    delimited: bool
    eof_terminated: bool
    field_counts: Mapping[str, int]
    missing_fields: tuple[str, ...]
    shape_defects: tuple[str, ...]
    timestamp_ns: int | None
    timestamp_seconds: float | None

    @property
    def complete(self) -> bool:
        return not self.missing_fields and not self.shape_defects


@dataclass(frozen=True)
class CompleteRecordScanResult:
    """Accepted complete prefix plus immutable byte/line source evidence."""

    policy: CompleteRecordPolicy
    source_path: Path
    records: tuple[HartleyInputRecord, ...]
    physical_records: tuple[PhysicalRecordEvidence, ...]
    raw_sha256: str
    raw_size_bytes: int
    raw_line_count: int
    raw_crlf_count: int
    raw_bare_lf_count: int
    raw_mtime_ns_before: int
    raw_mtime_ns_after: int
    raw_sha256_after: str
    raw_before_after_identity_match: bool
    prefix_sha256: str
    prefix_end_exclusive: int
    prefix_bytes: int
    tail_sha256: str
    tail_bytes: int
    first_complete_timestamp_ns: int
    last_complete_timestamp_ns: int
    duration_ns: int
    first_complete_timestamp_seconds: float
    last_complete_timestamp_seconds: float
    duration_seconds: float

    @property
    def complete_record_count(self) -> int:
        return len(self.records)

    @property
    def physical_record_start_count(self) -> int:
        return len(self.physical_records)

    @property
    def incomplete_record_count(self) -> int:
        return sum(not item.complete for item in self.physical_records)


@dataclass(frozen=True)
class HartleyInputRecord:
    """The complete and exclusive online projection admitted by H0--H2."""

    sec: int
    nanosec: int
    gyroscope: tuple[float, float, float]
    accelerometer: tuple[float, float, float]
    foot_force: tuple[float, float, float, float]
    foot_position_body: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    foot_speed_body: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    gait_type: str
    mode: str | None

    @property
    def timestamp_seconds(self) -> float:
        return self.sec + self.nanosec * 1.0e-9

    @property
    def timestamp_ns(self) -> int:
        return self.sec * 1_000_000_000 + self.nanosec


@dataclass(frozen=True)
class HartleyAuditPaths:
    config_path: Path
    raw_root: Path
    clean_root: Path
    by2_source: Path
    by2_hash_lock: Path
    default_output_root: Path


@dataclass(frozen=True)
class ContactDetectorConfig:
    on_threshold_by_native_leg: tuple[float, float, float, float]
    off_threshold_by_native_leg: tuple[float, float, float, float]
    minimum_dwell_seconds: float
    minimum_dwell_samples_source: int

    def __post_init__(self) -> None:
        on = np.asarray(self.on_threshold_by_native_leg, dtype=float)
        off = np.asarray(self.off_threshold_by_native_leg, dtype=float)
        if on.shape != (4,) or off.shape != (4,):
            raise RequiredFieldError("contact thresholds must contain four native-leg values")
        if np.any(~np.isfinite(on)) or np.any(~np.isfinite(off)):
            raise RequiredFieldError("contact thresholds must be finite")
        if np.any(on <= off):
            raise RequiredFieldError("each contact-on threshold must exceed contact-off")
        if not math.isfinite(self.minimum_dwell_seconds) or self.minimum_dwell_seconds <= 0.0:
            raise RequiredFieldError("minimum contact dwell must be positive and finite")
        if self.minimum_dwell_samples_source < 1:
            raise RequiredFieldError("minimum dwell sample source must be positive")


_INTEGER = re.compile(r"^[+-]?\d+$")
_LOCK_NONNEGATIVE_INTEGER = re.compile(r"^(?:0|[1-9][0-9]*)$")
_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LOCK_ROLE = re.compile(r"^[A-Z0-9_]+$")
_LOCK_LINE_COUNT = re.compile(r"^line_count:(0|[1-9][0-9]*)$")
_LOCK_FILE_TYPE = re.compile(r"^file_type:extension/[a-z0-9]+$")

PRODUCTION_COMPLETE_RECORD_POLICY_V1 = CompleteRecordPolicy(
    policy_id=BY2_COMPLETE_RECORD_POLICY_ID,
    expected_raw_sha256=PRODUCTION_BY2_RAW_SHA256,
    expected_raw_size_bytes=PRODUCTION_BY2_RAW_SIZE_BYTES,
    expected_raw_line_count=PRODUCTION_BY2_RAW_LINE_COUNT,
    expected_physical_record_starts=EXPECTED_BY2_MESSAGE_COUNT,
    expected_complete_record_count=EXPECTED_BY2_USABLE_RECORD_COUNT,
    expected_incomplete_record_count=1,
    expected_eof_foot_speed_count=PRODUCTION_BY2_EOF_FOOT_SPEED_COUNT,
    expected_prefix_sha256=PRODUCTION_BY2_PREFIX_SHA256,
    expected_prefix_end_exclusive=PRODUCTION_BY2_PREFIX_END_EXCLUSIVE,
    expected_first_complete_timestamp_ns=PRODUCTION_BY2_FIRST_COMPLETE_TIMESTAMP_NS,
    expected_last_complete_timestamp_ns=PRODUCTION_BY2_LAST_COMPLETE_TIMESTAMP_NS,
    expected_duration_ns=PRODUCTION_BY2_DURATION_NS,
    expected_tail_sha256=PRODUCTION_BY2_TAIL_SHA256,
    expected_tail_bytes=PRODUCTION_BY2_TAIL_BYTES,
    expected_final_record_start_line=PRODUCTION_BY2_FINAL_RECORD_START_LINE,
    expected_eof_timestamp_ns=PRODUCTION_BY2_EOF_TIMESTAMP_NS,
    expected_crlf_count=PRODUCTION_BY2_CRLF_COUNT,
    expected_bare_lf_count=PRODUCTION_BY2_BARE_LF_COUNT,
)


def _strip_scalar_comment(text: str) -> str:
    value = text.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def _parse_integer(text: str, label: str) -> int:
    value = _strip_scalar_comment(text)
    if not _INTEGER.fullmatch(value):
        raise RequiredFieldError(f"{label} is not an integer")
    return int(value)


def _parse_number(text: str, label: str) -> float:
    value = _strip_scalar_comment(text)
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RequiredFieldError(f"{label} is not numeric") from exc
    if not math.isfinite(parsed):
        raise RequiredFieldError(f"{label} is not finite")
    return parsed


def _parse_text_scalar(text: str, label: str) -> str:
    value = _strip_scalar_comment(text)
    if not value:
        raise RequiredFieldError(f"{label} is empty")
    return value


def _parse_inline_numeric_array(text: str, label: str) -> list[float]:
    value = _strip_scalar_comment(text)
    if not (value.startswith("[") and value.endswith("]")):
        raise RequiredFieldError(f"{label} inline value is not a sequence")
    content = value[1:-1].strip()
    if not content:
        return []
    return [_parse_number(item, label) for item in content.split(",")]


def _group_xyz(values: Sequence[float], label: str) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    if len(values) != 12:
        raise RequiredFieldError(f"{label} has shape {len(values)}, expected 12")
    return tuple(
        tuple(float(item) for item in values[index : index + 3])
        for index in range(0, 12, 3)
    )  # type: ignore[return-value]


_PRIMARY_STRUCTURAL_FIELD_COUNTS = {
    "stamp.sec": 1,
    "stamp.nanosec": 1,
    "imu_state.gyroscope": 3,
    "imu_state.accelerometer": 3,
    "foot_force": 4,
    "foot_position_body": 12,
    "foot_speed_body": 12,
}
_AUDIT_REQUIRED_FIELD_COUNTS = {
    "gait_type": 1,
}
_EXPECTED_PROJECTED_FIELD_COUNTS = {
    **_PRIMARY_STRUCTURAL_FIELD_COUNTS,
    **_AUDIT_REQUIRED_FIELD_COUNTS,
}
_REQUIRED_NON_FOOT_SPEED_FIELDS = tuple(
    key for key in _EXPECTED_PROJECTED_FIELD_COUNTS if key != "foot_speed_body"
)


def _parse_physical_record_lines(
    lines: Iterable[str],
    *,
    message_number: int,
    require_complete: bool,
) -> tuple[
    HartleyInputRecord | None,
    dict[str, int],
    tuple[str, ...],
    tuple[str, ...],
    int | None,
    float | None,
]:
    """Parse one timestamp-started physical record without reading unknown values."""

    sec: int | None = None
    nanosec: int | None = None
    gyro: list[float] = []
    accel: list[float] = []
    force: list[float] = []
    foot_position: list[float] = []
    foot_speed: list[float] = []
    gait_type: str | None = None
    mode: str | None = None
    top = ""
    active_array = ""
    array_indent = -1
    scalar_counts = {"stamp.sec": 0, "stamp.nanosec": 0, "gait_type": 0, "mode": 0}

    def array_target(name: str) -> list[float]:
        if name == "gyroscope":
            return gyro
        if name == "accelerometer":
            return accel
        if name == "foot_force":
            return force
        if name == "foot_position_body":
            return foot_position
        if name == "foot_speed_body":
            return foot_speed
        raise AssertionError(f"unreachable projected array: {name}")

    saw_stamp_start = False
    for raw_line in lines:
            stripped = raw_line.strip()
            if stripped == "---":
                break
            if not stripped or stripped.startswith("#") or stripped == "...":
                continue

            indent = len(raw_line) - len(raw_line.lstrip(" "))
            if indent == 0 and not stripped.startswith("-") and ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                top = key
                active_array = ""
                array_indent = -1
                if key == "stamp":
                    saw_stamp_start = True
                    continue
                if key == "imu_state":
                    continue
                if key in {"foot_force", "foot_position_body", "foot_speed_body"}:
                    if value.strip():
                        array_target(key).extend(_parse_inline_numeric_array(value, key))
                    else:
                        active_array = key
                        array_indent = indent
                    continue
                if key == "gait_type":
                    scalar_counts["gait_type"] += 1
                    gait_type = _parse_text_scalar(value, key)
                    continue
                if key == "mode":
                    scalar_counts["mode"] += 1
                    mode = _parse_text_scalar(value, key)
                    continue
                # Unknown top-level maps and scalars are skipped lexically.
                top = ""
                continue

            if top == "stamp" and ":" in stripped and not stripped.startswith("-"):
                key, value = stripped.split(":", 1)
                key = key.strip()
                if key == "sec":
                    scalar_counts["stamp.sec"] += 1
                    sec = _parse_integer(value, "stamp.sec")
                elif key == "nanosec":
                    scalar_counts["stamp.nanosec"] += 1
                    nanosec = _parse_integer(value, "stamp.nanosec")
                continue

            if top == "imu_state" and ":" in stripped and not stripped.startswith("-"):
                key, value = stripped.split(":", 1)
                key = key.strip()
                active_array = ""
                array_indent = -1
                if key in {"gyroscope", "accelerometer"}:
                    if value.strip():
                        array_target(key).extend(_parse_inline_numeric_array(value, key))
                    else:
                        active_array = key
                        array_indent = indent
                continue

            if active_array and indent >= array_indent and stripped.startswith("-"):
                array_target(active_array).append(_parse_number(stripped[1:], active_array))
                continue

    if not saw_stamp_start:
        raise RequiredFieldError(f"BY2 physical record {message_number} lacks a stamp start")
    field_counts = {
        **scalar_counts,
        "imu_state.gyroscope": len(gyro),
        "imu_state.accelerometer": len(accel),
        "foot_force": len(force),
        "foot_position_body": len(foot_position),
        "foot_speed_body": len(foot_speed),
    }
    missing_fields = tuple(
        key for key, expected in _EXPECTED_PROJECTED_FIELD_COUNTS.items()
        if field_counts[key] == 0 and expected > 0
    )
    shape_defects = tuple(
        f"{key}[{field_counts[key]}!={expected}]"
        for key, expected in _EXPECTED_PROJECTED_FIELD_COUNTS.items()
        if field_counts[key] != 0 and field_counts[key] != expected
    )
    if scalar_counts["mode"] > 1:
        shape_defects += (f"mode[{scalar_counts['mode']}!=0_or_1]",)
    defects = (*missing_fields, *shape_defects)
    if require_complete and defects:
        raise RequiredFieldError(
            f"BY2 projected message {message_number} is incomplete: {','.join(defects)}"
        )
    timestamp_seconds: float | None = None
    timestamp_ns: int | None = None
    if sec is not None and nanosec is not None:
        if not 0 <= nanosec < 1_000_000_000:
            raise RequiredFieldError(
                f"BY2 projected message {message_number} has nanosec outside [0,1e9)"
            )
        timestamp_ns = sec * 1_000_000_000 + nanosec
        timestamp_seconds = sec + nanosec * 1.0e-9
    if defects:
        return (
            None,
            field_counts,
            missing_fields,
            shape_defects,
            timestamp_ns,
            timestamp_seconds,
        )
    assert sec is not None and nanosec is not None and gait_type is not None
    record = HartleyInputRecord(
        sec=sec,
        nanosec=nanosec,
        gyroscope=tuple(gyro),  # type: ignore[arg-type]
        accelerometer=tuple(accel),  # type: ignore[arg-type]
        foot_force=tuple(force),  # type: ignore[arg-type]
        foot_position_body=_group_xyz(foot_position, "foot_position_body"),
        foot_speed_body=_group_xyz(foot_speed, "foot_speed_body"),
        gait_type=gait_type,
        mode=mode,
    )
    return (
        record,
        field_counts,
        missing_fields,
        shape_defects,
        timestamp_ns,
        timestamp_seconds,
    )


def iter_hartley_input_projection(path: str | Path) -> Iterator[HartleyInputRecord]:
    """Stream structurally complete records; no incomplete-EOF exception is implicit."""

    source = Path(path)
    active_lines: list[str] = []
    message_number = 0
    with source.open("r", encoding="utf-8", errors="strict", newline="") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            is_start = raw_line == "stamp:\n" or raw_line == "stamp:\r\n" or stripped == "stamp:"
            if is_start and not raw_line[:1].isspace():
                if active_lines:
                    raise RequiredFieldError(
                        f"BY2 projected message {message_number} is not delimiter-terminated"
                    )
                message_number += 1
                active_lines = [raw_line]
                continue
            if active_lines:
                active_lines.append(raw_line)
                if stripped == "---":
                    item, _counts, _missing, _defects, _timestamp_ns, _timestamp = _parse_physical_record_lines(
                        active_lines, message_number=message_number, require_complete=True
                    )
                    assert item is not None
                    yield item
                    active_lines = []
        if active_lines:
            item, _counts, _missing, _defects, _timestamp_ns, _timestamp = _parse_physical_record_lines(
                active_lines, message_number=message_number, require_complete=True
            )
            assert item is not None
            yield item


def scan_hartley_complete_record_prefix(
    path: str | Path,
    *,
    policy: CompleteRecordPolicy = PRODUCTION_COMPLETE_RECORD_POLICY_V1,
) -> CompleteRecordScanResult:
    """Apply the explicit V1 EOF exception after a strict binary source scan."""

    source = Path(path)
    before = source.stat()
    digest = hashlib.sha256()
    prefix_digest: str | None = None
    prefix_end_exclusive: int | None = None
    raw_line_count = 0
    raw_crlf_count = 0
    raw_bare_lf_count = 0
    byte_offset = 0
    record_lines: list[str] = []
    record_start_byte = 0
    record_start_line = 0
    physical: list[PhysicalRecordEvidence] = []
    accepted: list[HartleyInputRecord] = []

    def finish_record(
        *,
        end_byte_exclusive: int,
        end_line: int,
        delimiter_line: int | None,
        eof_terminated: bool,
    ) -> None:
        nonlocal record_lines, prefix_digest, prefix_end_exclusive
        record_index = len(physical) + 1
        (
            parsed,
            counts,
            missing,
            defects,
            timestamp_ns,
            timestamp_seconds,
        ) = _parse_physical_record_lines(
            record_lines,
            message_number=record_index,
            require_complete=False,
        )
        evidence = PhysicalRecordEvidence(
            record_index=record_index,
            start_byte=record_start_byte,
            end_byte_exclusive=end_byte_exclusive,
            start_line=record_start_line,
            end_line=end_line,
            delimiter_line=delimiter_line,
            delimited=delimiter_line is not None,
            eof_terminated=eof_terminated,
            field_counts=dict(counts),
            missing_fields=missing,
            shape_defects=defects,
            timestamp_ns=timestamp_ns,
            timestamp_seconds=timestamp_seconds,
        )
        physical.append(evidence)
        if parsed is not None:
            accepted.append(parsed)
            if delimiter_line is not None:
                prefix_digest = digest.copy().hexdigest()
                prefix_end_exclusive = end_byte_exclusive
        record_lines = []

    with source.open("rb") as handle:
        for binary_line in handle:
            line_start = byte_offset
            byte_offset += len(binary_line)
            digest.update(binary_line)
            raw_line_count += 1
            if binary_line.endswith(b"\r\n"):
                raw_crlf_count += 1
            elif binary_line.endswith(b"\n"):
                raw_bare_lf_count += 1
            try:
                text_line = binary_line.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise RequiredFieldError(
                    f"raw source is not strict UTF-8 at byte {line_start}"
                ) from exc
            stripped = text_line.strip()
            is_start = stripped == "stamp:" and not text_line[:1].isspace()
            if is_start:
                if record_lines:
                    finish_record(
                        end_byte_exclusive=line_start,
                        end_line=raw_line_count - 1,
                        delimiter_line=None,
                        eof_terminated=False,
                    )
                record_start_byte = line_start
                record_start_line = raw_line_count
                record_lines = [text_line]
                continue
            if record_lines:
                record_lines.append(text_line)
                if stripped == "---":
                    finish_record(
                        end_byte_exclusive=byte_offset,
                        end_line=raw_line_count,
                        delimiter_line=raw_line_count,
                        eof_terminated=False,
                    )
        if record_lines:
            finish_record(
                end_byte_exclusive=byte_offset,
                end_line=raw_line_count,
                delimiter_line=None,
                eof_terminated=True,
            )

    raw_sha256 = digest.hexdigest()
    after = source.stat()
    raw_sha256_after = sha256_file(source)
    identity_match = (
        before.st_size == after.st_size == byte_offset
        and before.st_mtime_ns == after.st_mtime_ns
        and raw_sha256 == raw_sha256_after
    )
    if not identity_match:
        raise HartleyH0H2Error("raw source identity changed during complete-record scan")
    identity_actual = (
        raw_sha256,
        byte_offset,
        raw_line_count,
    )
    identity_expected = (
        policy.expected_raw_sha256,
        policy.expected_raw_size_bytes,
        policy.expected_raw_line_count,
    )
    if identity_actual != identity_expected:
        raise HartleyH0H2Error(
            "complete-record policy source SHA/size/line identity is unapproved"
        )
    if len(physical) != policy.expected_physical_record_starts:
        raise RequiredFieldError(
            "physical timestamp-start count does not match complete-record policy"
        )
    incomplete = [item for item in physical if not item.complete]
    if len(incomplete) != policy.expected_incomplete_record_count:
        raise RequiredFieldError(
            f"complete-record policy requires exactly {policy.expected_incomplete_record_count} "
            f"incomplete physical record(s), found {len(incomplete)}"
        )
    if any(not item.complete or not item.delimited for item in physical[:-1]):
        raise RequiredFieldError(
            "incomplete interior/delimited or undelimited interior physical record"
        )
    final = physical[-1]
    if final.complete or final.delimited or not final.eof_terminated:
        raise RequiredFieldError("complete-record policy requires one incomplete physical EOF record")
    expected_final_defect = (
        f"foot_speed_body[{policy.expected_eof_foot_speed_count}!=12]",
    )
    if final.missing_fields or final.shape_defects != expected_final_defect:
        primary_missing = tuple(
            field for field in _REQUIRED_NON_FOOT_SPEED_FIELDS
            if final.field_counts.get(field, 0) != _EXPECTED_PROJECTED_FIELD_COUNTS[field]
        )
        detail = ",".join((*primary_missing, *final.missing_fields, *final.shape_defects))
        raise RequiredFieldError(
            "physical EOF record does not have the sole authorized foot_speed shape defect: "
            + detail
        )
    if len(accepted) != policy.expected_complete_record_count:
        raise RequiredFieldError("usable complete-prefix count does not match policy")
    if prefix_digest is None or prefix_end_exclusive is None:
        raise RequiredFieldError("complete-record prefix byte boundary was not established")
    if policy.expected_prefix_sha256 is not None and (
        prefix_digest != policy.expected_prefix_sha256
    ):
        raise RequiredFieldError("complete-record prefix SHA256 does not match policy")
    if policy.expected_prefix_end_exclusive is not None and (
        prefix_end_exclusive != policy.expected_prefix_end_exclusive
    ):
        raise RequiredFieldError("complete-record prefix byte boundary does not match policy")
    first_ns = accepted[0].timestamp_ns
    last_ns = accepted[-1].timestamp_ns
    duration_ns = last_ns - first_ns
    if policy.expected_first_complete_timestamp_ns is not None and (
        first_ns != policy.expected_first_complete_timestamp_ns
    ):
        raise RequiredFieldError("first complete timestamp does not match policy")
    if policy.expected_last_complete_timestamp_ns is not None and (
        last_ns != policy.expected_last_complete_timestamp_ns
    ):
        raise RequiredFieldError("last complete timestamp does not match policy")
    if policy.expected_duration_ns is not None and duration_ns != policy.expected_duration_ns:
        raise RequiredFieldError("complete-prefix integer duration does not match policy")
    with source.open("rb") as handle:
        handle.seek(prefix_end_exclusive)
        tail = handle.read()
    tail_sha256 = hashlib.sha256(tail).hexdigest()
    result = CompleteRecordScanResult(
        policy=policy,
        source_path=source,
        records=tuple(accepted),
        physical_records=tuple(physical),
        raw_sha256=raw_sha256,
        raw_size_bytes=byte_offset,
        raw_line_count=raw_line_count,
        raw_crlf_count=raw_crlf_count,
        raw_bare_lf_count=raw_bare_lf_count,
        raw_mtime_ns_before=before.st_mtime_ns,
        raw_mtime_ns_after=after.st_mtime_ns,
        raw_sha256_after=raw_sha256_after,
        raw_before_after_identity_match=identity_match,
        prefix_sha256=prefix_digest,
        prefix_end_exclusive=prefix_end_exclusive,
        prefix_bytes=prefix_end_exclusive,
        tail_sha256=tail_sha256,
        tail_bytes=len(tail),
        first_complete_timestamp_ns=first_ns,
        last_complete_timestamp_ns=last_ns,
        duration_ns=duration_ns,
        first_complete_timestamp_seconds=first_ns / 1.0e9,
        last_complete_timestamp_seconds=last_ns / 1.0e9,
        duration_seconds=duration_ns / 1.0e9,
    )
    optional_signature = (
        policy.expected_tail_bytes,
        policy.expected_tail_sha256,
        policy.expected_final_record_start_line,
        policy.expected_eof_timestamp_ns,
        policy.expected_crlf_count,
        policy.expected_bare_lf_count,
    )
    if any(value is not None for value in optional_signature):
        actual_signature = (
            result.tail_bytes,
            result.tail_sha256,
            final.start_line,
            final.timestamp_ns,
            result.raw_crlf_count,
            result.raw_bare_lf_count,
        )
        if actual_signature != optional_signature:
            raise RequiredFieldError("EOF/newline signature does not match policy")
    return result


def complete_record_prefix_manifest(scan: CompleteRecordScanResult) -> dict[str, Any]:
    """Return the exact accepted byte interval and immutable source identity."""

    first = scan.records[0]
    last = scan.records[-1]
    mandatory_shapes = {
        "primary_structural_per_physical_record": dict(
            _PRIMARY_STRUCTURAL_FIELD_COUNTS
        ),
        "audit_required_per_physical_record": dict(_AUDIT_REQUIRED_FIELD_COUNTS),
        "accepted_projected_arrays": {
            "gyroscope": [scan.complete_record_count, 3],
            "accelerometer": [scan.complete_record_count, 3],
            "foot_force": [scan.complete_record_count, 4],
            "foot_position_body": [scan.complete_record_count, 4, 3],
            "foot_speed_body": [scan.complete_record_count, 4, 3],
        },
    }
    return {
        "schema_version": "hartley.by2_complete_record_prefix_manifest.v1",
        "policy_id": scan.policy.policy_id,
        "data_identity": "REAL_BY2_COMPLETE_RECORD_PREFIX_63277",
        "data_status": "REAL_BY2_COMPLETE_RECORD_PREFIX",
        "data_mode": "real_by2_raw",
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "raw_source_path_alias": f"<RAW_ROOT>/{BY2_RELATIVE_PATH}",
        "raw_source_sha256": scan.raw_sha256,
        "raw_source_size": scan.raw_size_bytes,
        "raw_source_line_count": scan.raw_line_count,
        "raw_sha256": scan.raw_sha256,
        "raw_size_bytes": scan.raw_size_bytes,
        "raw_line_count": scan.raw_line_count,
        "raw_crlf_count": scan.raw_crlf_count,
        "raw_bare_lf_count": scan.raw_bare_lf_count,
        "raw_sha256_after": scan.raw_sha256_after,
        "raw_mtime_ns_before": scan.raw_mtime_ns_before,
        "raw_mtime_ns_after": scan.raw_mtime_ns_after,
        "raw_before_after_identity_match": scan.raw_before_after_identity_match,
        "physical_record_start_token": "stamp:",
        "physical_record_start_count": scan.physical_record_start_count,
        "complete_record_count": scan.complete_record_count,
        "trailing_incomplete_record_count": scan.incomplete_record_count,
        "incomplete_record_count": scan.incomplete_record_count,
        "raw_source_complete": False,
        "complete_record_prefix_filter_eligible": True,
        "accepted_prefix_interval": [0, scan.prefix_end_exclusive],
        "prefix_end_exclusive": scan.prefix_end_exclusive,
        "complete_prefix_end_byte_offset": scan.prefix_end_exclusive,
        "prefix_bytes": scan.prefix_bytes,
        "prefix_sha256": scan.prefix_sha256,
        "complete_prefix_sha256": scan.prefix_sha256,
        "mandatory_field_shapes": dict(_PRIMARY_STRUCTURAL_FIELD_COUNTS),
        "audit_required_field_shapes": dict(_AUDIT_REQUIRED_FIELD_COUNTS),
        "mandatory_field_shape_summary": mandatory_shapes,
        "first_complete_record_start_byte": scan.physical_records[0].start_byte,
        "first_complete_record_start_line": scan.physical_records[0].start_line,
        "last_complete_record_start_byte": scan.physical_records[-2].start_byte,
        "last_complete_record_end_byte_exclusive": (
            scan.physical_records[-2].end_byte_exclusive
        ),
        "last_complete_record_start_line": scan.physical_records[-2].start_line,
        "last_complete_record_end_line": scan.physical_records[-2].end_line,
        "first_complete_timestamp_ns": scan.first_complete_timestamp_ns,
        "last_complete_timestamp_ns": scan.last_complete_timestamp_ns,
        "first_complete_timestamp": {
            "sec": first.sec,
            "nanosec": first.nanosec,
            "ns": first.timestamp_ns,
        },
        "last_complete_timestamp": {
            "sec": last.sec,
            "nanosec": last.nanosec,
            "ns": last.timestamp_ns,
        },
        "duration_ns": scan.duration_ns,
        "complete_prefix_duration": scan.duration_seconds,
        "complete_prefix_duration_ns": scan.duration_ns,
        "complete_prefix_duration_exact": f"{scan.duration_ns} ns",
        "first_complete_timestamp_seconds": scan.first_complete_timestamp_seconds,
        "last_complete_timestamp_seconds": scan.last_complete_timestamp_seconds,
        "duration_seconds": scan.duration_seconds,
        "record_separator_included_in_prefix": True,
        "raw_mutated": False,
        "raw_source_mutated": False,
        "imputation_used": False,
        "no_imputation": True,
        "interpolation_used": False,
        "no_interpolation": True,
    }


def trailing_record_ledger(scan: CompleteRecordScanResult) -> dict[str, Any]:
    """Return exact evidence for the one whole-record EOF exclusion."""

    final = scan.physical_records[-1]
    return {
        "schema_version": "hartley.by2_trailing_record_ledger.v1",
        "policy_id": scan.policy.policy_id,
        "data_identity": "REAL_BY2_COMPLETE_RECORD_PREFIX_63277",
        "data_status": "REAL_BY2_COMPLETE_RECORD_PREFIX",
        "raw_source_complete": False,
        "complete_record_prefix_filter_eligible": True,
        "trailing_incomplete_record_count": 1,
        "action": "DROP_ENTIRE_INCOMPLETE_PHYSICAL_EOF_RECORD",
        "partial_record_contributes_projection_row": False,
        "trailing_record_used_online": False,
        "tail_start_byte": final.start_byte,
        "tail_end_byte_exclusive": final.end_byte_exclusive,
        "tail_bytes": scan.tail_bytes,
        "tail_sha256": scan.tail_sha256,
        "start_line": final.start_line,
        "end_line": final.end_line,
        "delimiter_line": final.delimiter_line,
        "eof_terminated": final.eof_terminated,
        "record_index": final.record_index,
        "timestamp_ns": final.timestamp_ns,
        "timestamp_seconds": final.timestamp_seconds,
        "field_counts": dict(final.field_counts),
        "missing_fields": list(final.missing_fields),
        "exact_missing_fields": ["foot_speed_body[4:12]"],
        "exact_missing_field_values": {
            "foot_speed_body": {
                "present_count": 4,
                "expected_count": 12,
                "missing_count": 8,
                "missing_indices": list(range(4, 12)),
            }
        },
        "values": {
            "foot_speed_body_present_count": 4,
            "foot_speed_body_expected_count": 12,
            "foot_speed_body_missing_count": 8,
            "foot_speed_body_missing_indices": list(range(4, 12)),
        },
        "shape_defects": list(final.shape_defects),
        "primary_field_defects": [
            field for field in _PRIMARY_STRUCTURAL_FIELD_COUNTS
            if final.field_counts.get(field, 0) != _EXPECTED_PROJECTED_FIELD_COUNTS[field]
        ],
        "audit_required_field_defects": [
            field for field in _AUDIT_REQUIRED_FIELD_COUNTS
            if final.field_counts.get(field, 0) != _EXPECTED_PROJECTED_FIELD_COUNTS[field]
        ],
        "only_shape_defect_is_foot_speed_4_of_12": (
            final.shape_defects == ("foot_speed_body[4!=12]",)
            and not final.missing_fields
        ),
        "foot_speed_role": "DIAGNOSTIC_ONLY",
        "foot_speed_online_allowed": False,
        "foot_speed_changes_threshold_or_state": False,
        "imputation_used": False,
        "interpolation_used": False,
        "raw_mutated": False,
    }


def _resolved_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HartleyH0H2Error(f"resolved source escapes configured raw root: {relative}") from exc
    if not candidate.is_file():
        raise HartleyH0H2Error(f"resolved source is not a regular file: {relative}")
    return candidate


def resolve_hartley_audit_paths(config_path: str | Path) -> HartleyAuditPaths:
    """Resolve the canonical BY2 source only from the ignored local aliases."""

    config = Path(config_path).resolve(strict=True)
    document = yaml.safe_load(config.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != "paper_rebuild.paths.v1":
        raise HartleyH0H2Error("unsupported local path-alias schema")
    values = document.get("paths")
    if not isinstance(values, dict):
        raise HartleyH0H2Error("local path-alias mapping is absent")
    if not isinstance(values.get("raw_root"), str) or not isinstance(values.get("clean_root"), str):
        raise HartleyH0H2Error("local path aliases omit raw_root or clean_root")
    raw_root = Path(values["raw_root"]).resolve(strict=True)
    clean_root = Path(values["clean_root"]).resolve(strict=True)
    if not raw_root.is_dir() or not clean_root.is_dir():
        raise HartleyH0H2Error("configured raw_root or clean_root is not a directory")
    source = _resolved_child(raw_root, BY2_RELATIVE_PATH)
    configured_source = values.get("by2_go2_body")
    if configured_source is not None:
        if not isinstance(configured_source, str):
            raise HartleyH0H2Error("by2_go2_body local alias is not a string")
        if Path(configured_source).resolve(strict=True) != source:
            raise HartleyH0H2Error(
                "by2_go2_body alias disagrees with raw_root plus canonical relative path"
            )
    lock = (clean_root / "01_RAW_HASH_LOCK/BY2_HASH_LOCK.csv").resolve(strict=True)
    if not lock.is_file():
        raise HartleyH0H2Error("BY2 hash lock is unavailable")
    return HartleyAuditPaths(
        config_path=config,
        raw_root=raw_root,
        clean_root=clean_root,
        by2_source=source,
        by2_hash_lock=lock,
        default_output_root=clean_root / HARTLEY_INPUT_AUDIT_RELATIVE,
    )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_by2_hash_lock(paths: HartleyAuditPaths) -> dict[str, Any]:
    actual_lock_sha256 = sha256_file(paths.by2_hash_lock)
    if not _LOWER_SHA256.fullmatch(TRUSTED_BY2_HASH_LOCK_SHA256):
        raise HartleyH0H2Error("trusted BY2 hash-lock SHA256 constant is malformed")
    if actual_lock_sha256 != TRUSTED_BY2_HASH_LOCK_SHA256:
        raise HartleyH0H2Error("BY2 hash-lock SHA256 does not match the trusted identity")

    with paths.by2_hash_lock.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != BY2_HASH_LOCK_COLUMNS:
            raise HartleyH0H2Error("BY2 hash-lock columns do not match the strict schema")
        rows = list(reader)
    if not rows:
        raise HartleyH0H2Error("BY2 hash lock contains no rows")

    seen_paths: set[str] = set()
    for row_index, item in enumerate(rows, start=2):
        if tuple(item) != BY2_HASH_LOCK_COLUMNS or any(value is None for value in item.values()):
            raise HartleyH0H2Error(f"BY2 hash-lock row {row_index} violates the strict schema")
        relative = item["relative_path"]
        posix = PurePosixPath(relative)
        if (
            not relative
            or relative.startswith("/")
            or "\\" in relative
            or posix.as_posix() != relative
            or any(part in {"", ".", ".."} for part in posix.parts)
        ):
            raise HartleyH0H2Error(f"BY2 hash-lock row {row_index} has an invalid relative path")
        if relative in seen_paths:
            raise HartleyH0H2Error(f"BY2 hash-lock path is duplicated: {relative}")
        seen_paths.add(relative)
        if not _LOCK_NONNEGATIVE_INTEGER.fullmatch(item["size_bytes"]):
            raise HartleyH0H2Error(f"BY2 hash-lock row {row_index} has an invalid size")
        count_or_type = item["line_count_or_file_type"]
        if not (
            _LOCK_LINE_COUNT.fullmatch(count_or_type)
            or _LOCK_FILE_TYPE.fullmatch(count_or_type)
        ):
            raise HartleyH0H2Error(
                f"BY2 hash-lock row {row_index} has an invalid line-count/file-type value"
            )
        if not _LOWER_SHA256.fullmatch(item["sha256"]):
            raise HartleyH0H2Error(f"BY2 hash-lock row {row_index} has an invalid SHA256")
        if not _LOCK_ROLE.fullmatch(item["role"]):
            raise HartleyH0H2Error(f"BY2 hash-lock row {row_index} has an invalid role")
        if item["dataset"] != "BY2" or item["immutable"] != "true":
            raise HartleyH0H2Error(f"BY2 hash-lock row {row_index} violates dataset immutability")
        if not _LOCK_NONNEGATIVE_INTEGER.fullmatch(item["mtime_ns"]):
            raise HartleyH0H2Error(f"BY2 hash-lock row {row_index} has an invalid mtime")

    canonical_rows = [item for item in rows if item["relative_path"] == BY2_RELATIVE_PATH]
    if len(canonical_rows) != 1:
        raise HartleyH0H2Error(
            "BY2 hash lock must contain exactly one canonical body-source row"
        )
    row = canonical_rows[0]
    if not _LOCK_LINE_COUNT.fullmatch(row["line_count_or_file_type"]):
        raise HartleyH0H2Error("canonical BY2 body source lacks a locked line count")
    locked_size = int(row["size_bytes"])
    size = paths.by2_source.stat().st_size
    digest = sha256_file(paths.by2_source)
    if size != locked_size or digest != row["sha256"]:
        raise HartleyH0H2Error("canonical BY2 body source fails its hash lock")
    return {
        "path_alias": f"<RAW_ROOT>/{BY2_RELATIVE_PATH}",
        "relative_path": BY2_RELATIVE_PATH,
        "size_bytes": size,
        "sha256": digest,
        "locked_line_count": int(row["line_count_or_file_type"].split(":", 1)[1]),
        "hash_lock_alias": "<CLEAN_ROOT>/01_RAW_HASH_LOCK/BY2_HASH_LOCK.csv",
        "hash_lock_sha256": actual_lock_sha256,
        "hash_lock_trusted_identity_verified": True,
    }


def native_to_canonical_foot_order(values: Sequence[Any] | np.ndarray) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim < 1 or array.shape[0] != 4:
        raise RequiredFieldError("native foot array must have leading dimension four")
    return array[np.asarray(NATIVE_TO_CANONICAL)].copy()


def canonical_to_native_foot_order(values: Sequence[Any] | np.ndarray) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim < 1 or array.shape[0] != 4:
        raise RequiredFieldError("canonical foot array must have leading dimension four")
    return array[np.asarray(CANONICAL_TO_NATIVE)].copy()


def euler_rpy_deg_to_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    roll, pitch, yaw = map(math.radians, (roll_deg, pitch_deg, yaw_deg))
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array(((1.0, 0.0, 0.0), (0.0, cr, -sr), (0.0, sr, cr)))
    ry = np.array(((cp, 0.0, sp), (0.0, 1.0, 0.0), (-sp, 0.0, cp)))
    rz = np.array(((cy, -sy, 0.0), (sy, cy, 0.0), (0.0, 0.0, 1.0)))
    return rz @ ry @ rx


def installation_rotation_candidates() -> dict[str, np.ndarray]:
    """Return both physical interpretations without silently selecting one."""

    active = euler_rpy_deg_to_matrix(*IMU_INSTALL_RPY_DEG)
    return {
        "SENSOR_TO_BODY_ACTIVE_RZRYRX": active,
        "BODY_TO_SENSOR_ACTIVE_RZRYRX_INVERTED": active.T,
    }


def hartley_world_up_gauge_to_reporting_down_gauge() -> np.ndarray:
    """Flip a chosen world-up reporting gauge into its reporting-down gauge.

    The two horizontal axes are initialization/reporting gauge axes only.  The
    first axis is not an observed north direction, and this proper rotation
    must never be presented as creating an absolute heading measurement.
    """

    return np.diag((1.0, -1.0, -1.0))


def validate_rotation_matrix(matrix: Sequence[Sequence[float]], *, atol: float = 1.0e-12) -> dict[str, Any]:
    rotation = np.asarray(matrix, dtype=float)
    if rotation.shape != (3, 3) or np.any(~np.isfinite(rotation)):
        raise RequiredFieldError("frame transform must be a finite 3x3 matrix")
    orthogonality_error = float(np.linalg.norm(rotation @ rotation.T - np.eye(3), ord="fro"))
    determinant = float(np.linalg.det(rotation))
    return {
        "determinant": determinant,
        "orthogonality_error_fro": orthogonality_error,
        "right_handed": abs(determinant - 1.0) <= atol,
        "round_trip_error_fro": float(np.linalg.norm(rotation.T @ rotation - np.eye(3), ord="fro")),
        "passed": (
            abs(determinant - 1.0) <= atol
            and orthogonality_error <= atol
        ),
    }


def stationary_gravity_cancellation(
    accelerometer_sensor_mps2: Sequence[Sequence[float]] | np.ndarray,
    sensor_to_body: Sequence[Sequence[float]] | np.ndarray,
) -> dict[str, Any]:
    samples = np.asarray(accelerometer_sensor_mps2, dtype=float)
    rotation = np.asarray(sensor_to_body, dtype=float)
    check = validate_rotation_matrix(rotation)
    if not check["passed"]:
        raise RequiredFieldError("sensor-to-body candidate is not a proper rotation")
    if samples.ndim != 2 or samples.shape[1] != 3 or len(samples) < 1:
        raise RequiredFieldError("stationary acceleration must have shape Nx3")
    if np.any(~np.isfinite(samples)):
        raise RequiredFieldError("stationary acceleration contains nonfinite values")
    mean_body = np.mean((rotation @ samples.T).T, axis=0)
    gravity = float(np.linalg.norm(mean_body))
    if gravity <= NUMERICAL_TOLERANCE:
        raise RequiredFieldError("stationary acceleration has zero gravity magnitude")
    expected_specific_force = np.array((0.0, 0.0, gravity))
    world_gravity = np.array((0.0, 0.0, -gravity))
    propagation_residual = mean_body + world_gravity
    return {
        "mean_specific_force_body_mps2": mean_body.tolist(),
        "estimated_gravity_mps2": gravity,
        "expected_stationary_specific_force_body_mps2": expected_specific_force.tolist(),
        "stationary_specific_force_error_mps2": float(
            np.linalg.norm(mean_body - expected_specific_force)
        ),
        "propagation_gravity_cancellation_norm_mps2": float(
            np.linalg.norm(propagation_residual)
        ),
    }


def _record_arrays(records: Sequence[HartleyInputRecord]) -> dict[str, np.ndarray]:
    if not records:
        raise RequiredFieldError("BY2 projected stream is empty")
    arrays = {
        "time": np.asarray([row.timestamp_seconds for row in records], dtype=float),
        "gyroscope": np.asarray([row.gyroscope for row in records], dtype=float),
        "accelerometer": np.asarray([row.accelerometer for row in records], dtype=float),
        "foot_force": np.asarray([row.foot_force for row in records], dtype=float),
        "foot_position_body": np.asarray([row.foot_position_body for row in records], dtype=float),
        "foot_speed_body": np.asarray([row.foot_speed_body for row in records], dtype=float),
    }
    expected_shapes = {
        "time": (len(records),),
        "gyroscope": (len(records), 3),
        "accelerometer": (len(records), 3),
        "foot_force": (len(records), 4),
        "foot_position_body": (len(records), 4, 3),
        "foot_speed_body": (len(records), 4, 3),
    }
    for key, expected in expected_shapes.items():
        if arrays[key].shape != expected or np.any(~np.isfinite(arrays[key])):
            raise RequiredFieldError(f"projected {key} array violates finite shape {expected}")
    return arrays


def timing_audit(records: Sequence[HartleyInputRecord]) -> dict[str, Any]:
    _record_arrays(records)
    timestamp_ns = np.asarray([row.timestamp_ns for row in records], dtype=np.int64)
    differences_ns = np.diff(timestamp_ns)
    if len(differences_ns) and np.any(differences_ns <= 0):
        bad = int(np.flatnonzero(differences_ns <= 0)[0])
        raise RequiredFieldError(
            f"BY2 timestamps are not strictly monotonic at projected rows {bad}/{bad + 1}"
        )
    median_dt_ns = float(np.median(differences_ns)) if len(differences_ns) else 0.0
    duration_ns = int(timestamp_ns[-1] - timestamp_ns[0])
    return {
        "message_count": len(records),
        "first_timestamp_ns": int(timestamp_ns[0]),
        "last_timestamp_ns": int(timestamp_ns[-1]),
        "duration_ns": duration_ns,
        "first_timestamp_seconds": int(timestamp_ns[0]) / 1.0e9,
        "last_timestamp_seconds": int(timestamp_ns[-1]) / 1.0e9,
        "duration_seconds": duration_ns / 1.0e9,
        "float_timestamp_subtraction_authoritative": False,
        "strictly_monotonic": True,
        "minimum_dt_seconds": (
            int(np.min(differences_ns)) / 1.0e9 if len(differences_ns) else 0.0
        ),
        "median_dt_seconds": median_dt_ns / 1.0e9,
        "maximum_dt_seconds": (
            int(np.max(differences_ns)) / 1.0e9 if len(differences_ns) else 0.0
        ),
        "median_rate_hz": 1.0e9 / median_dt_ns if median_dt_ns > 0.0 else 0.0,
    }


def _numeric_summary(values: np.ndarray) -> dict[str, float | int]:
    data = np.asarray(values, dtype=float).reshape(-1)
    finite = data[np.isfinite(data)]
    if not len(finite):
        raise RequiredFieldError("distribution contains no finite values")
    quantiles = np.percentile(finite, (1, 5, 25, 50, 75, 95, 99), method="linear")
    return {
        "finite_count": int(len(finite)),
        "total_count": int(len(data)),
        "finite_rate": float(len(finite) / len(data)),
        "minimum": float(np.min(finite)),
        "p01": float(quantiles[0]),
        "p05": float(quantiles[1]),
        "p25": float(quantiles[2]),
        "p50": float(quantiles[3]),
        "p75": float(quantiles[4]),
        "p95": float(quantiles[5]),
        "p99": float(quantiles[6]),
        "maximum": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
    }


def _distribution_rows(
    values_by_leg: np.ndarray,
    *,
    quantity: str,
    histogram_bins: int = DEFAULT_HISTOGRAM_BINS,
) -> list[dict[str, Any]]:
    values = np.asarray(values_by_leg, dtype=float)
    if values.ndim != 2 or values.shape[1] != 4:
        raise RequiredFieldError(f"{quantity} distribution must have shape Nx4")
    if histogram_bins < 2:
        raise RequiredFieldError("histogram bin count must be at least two")
    rows: list[dict[str, Any]] = []
    for leg_index, leg in enumerate(NATIVE_FOOT_ORDER):
        leg_values = values[:, leg_index]
        summary = _numeric_summary(leg_values)
        rows.append({
            "row_type": "quantiles",
            "quantity": quantity,
            "native_leg_index": leg_index,
            "leg": leg,
            **summary,
            "bin_index": "",
            "bin_left": "",
            "bin_right": "",
            "bin_count": "",
        })
        counts, edges = np.histogram(leg_values, bins=histogram_bins)
        for bin_index, count in enumerate(counts):
            rows.append({
                "row_type": "histogram",
                "quantity": quantity,
                "native_leg_index": leg_index,
                "leg": leg,
                **{key: "" for key in summary},
                "bin_index": bin_index,
                "bin_left": float(edges[bin_index]),
                "bin_right": float(edges[bin_index + 1]),
                "bin_count": int(count),
            })
    return rows


def _two_force_modes(values: np.ndarray) -> dict[str, Any]:
    data = np.asarray(values, dtype=float).reshape(-1)
    if len(data) < 8 or np.any(~np.isfinite(data)):
        return {"identifiable": False, "reason": "INSUFFICIENT_FINITE_SAMPLES"}
    low, high = (float(item) for item in np.percentile(data, (20.0, 80.0), method="linear"))
    if high - low <= NUMERICAL_TOLERANCE:
        return {"identifiable": False, "reason": "FORCE_RANGE_COLLAPSED"}
    assignment = np.zeros(len(data), dtype=bool)
    for _iteration in range(100):
        midpoint = 0.5 * (low + high)
        new_assignment = data > midpoint
        if not np.any(new_assignment) or np.all(new_assignment):
            return {"identifiable": False, "reason": "TWO_MODES_HAVE_EMPTY_CLUSTER"}
        new_low = float(np.median(data[~new_assignment]))
        new_high = float(np.median(data[new_assignment]))
        if new_low > new_high:
            new_low, new_high = new_high, new_low
            new_assignment = ~new_assignment
        converged = (
            np.array_equal(new_assignment, assignment)
            and abs(new_low - low) <= NUMERICAL_TOLERANCE
            and abs(new_high - high) <= NUMERICAL_TOLERANCE
        )
        assignment = new_assignment
        low, high = new_low, new_high
        if converged:
            break
    low_count = int(np.sum(~assignment))
    high_count = int(np.sum(assignment))
    gap = high - low
    scale = max(abs(low), abs(high), float(np.ptp(data)), NUMERICAL_TOLERANCE)
    minimum_cluster_count = max(3, int(math.ceil(0.01 * len(data))))
    identifiable = (
        low_count >= minimum_cluster_count
        and high_count >= minimum_cluster_count
        and gap / scale >= 0.05
    )
    return {
        "identifiable": identifiable,
        "reason": "TWO_INPUT_FORCE_MODES_SEPARATED" if identifiable else "TWO_MODES_NOT_STABLE",
        "low_mode_median": low,
        "high_mode_median": high,
        "mode_gap": gap,
        "relative_mode_gap": gap / scale,
        "low_mode_count": low_count,
        "high_mode_count": high_count,
        "minimum_cluster_count": minimum_cluster_count,
        "off_threshold": low + 0.40 * gap,
        "on_threshold": low + 0.60 * gap,
    }


def derive_force_contact_proposal(
    records: Sequence[HartleyInputRecord],
    *,
    minimum_dwell_samples: int = DEFAULT_MINIMUM_DWELL_SAMPLES,
) -> tuple[ContactDetectorConfig | None, dict[str, Any]]:
    arrays = _record_arrays(records)
    timing = timing_audit(records)
    differences = np.diff(arrays["time"])
    measured_median_dt = float(np.median(differences)) if len(differences) else 0.0
    if minimum_dwell_samples < 1 or measured_median_dt <= 0.0:
        raise RequiredFieldError("input-derived dwell policy requires positive cadence")
    modes = {
        leg: _two_force_modes(arrays["foot_force"][:, index])
        for index, leg in enumerate(NATIVE_FOOT_ORDER)
    }
    identifiable = all(mode["identifiable"] for mode in modes.values())
    proposal: dict[str, Any] = {
        "schema_version": "hartley.contact_threshold_proposal.v1",
        "status": "INPUT_ONLY_PROPOSAL_IDENTIFIABLE" if identifiable else "INPUT_NOT_IDENTIFIABLE",
        "source_type": "BY2_PHYSICAL_INSTANTIATION",
        "decision_signal": "foot_force_only",
        "diagnostic_signal_not_used_for_decision": "foot_speed_body",
        "threshold_rule": (
            "per_leg_two_mode_medians;off=low+0.40*(high-low);"
            "on=low+0.60*(high-low)"
        ),
        "two_mode_initialization_quantiles": [0.20, 0.80],
        "minimum_mode_fraction": 0.01,
        "minimum_dwell_samples_source": minimum_dwell_samples,
        "minimum_dwell_seconds": minimum_dwell_samples * measured_median_dt,
        "median_dt_seconds": measured_median_dt,
        "exact_integer_timing_audit": timing,
        "native_foot_order": list(NATIVE_FOOT_ORDER),
        "per_leg": modes,
        "reference_tuned": False,
        "output_metric_tuned": False,
        "slip_rejection_enabled": False,
    }
    if not identifiable:
        return None, proposal
    config = ContactDetectorConfig(
        on_threshold_by_native_leg=tuple(
            float(modes[leg]["on_threshold"]) for leg in NATIVE_FOOT_ORDER
        ),  # type: ignore[arg-type]
        off_threshold_by_native_leg=tuple(
            float(modes[leg]["off_threshold"]) for leg in NATIVE_FOOT_ORDER
        ),  # type: ignore[arg-type]
        minimum_dwell_seconds=float(proposal["minimum_dwell_seconds"]),
        minimum_dwell_samples_source=minimum_dwell_samples,
    )
    return config, proposal


def force_hysteresis_contacts(
    timestamps_seconds: Sequence[float] | np.ndarray,
    foot_force: Sequence[Sequence[float]] | np.ndarray,
    config: ContactDetectorConfig,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Classify contacts from force alone using hysteresis and time dwell."""

    times = np.asarray(timestamps_seconds, dtype=float)
    forces = np.asarray(foot_force, dtype=float)
    if times.ndim != 1 or forces.shape != (len(times), 4) or not len(times):
        raise RequiredFieldError("force contact input must have shapes N and Nx4")
    if np.any(~np.isfinite(times)) or np.any(~np.isfinite(forces)) or np.any(np.diff(times) <= 0.0):
        raise RequiredFieldError("force contact inputs must be finite and strictly chronological")
    on = np.asarray(config.on_threshold_by_native_leg)
    off = np.asarray(config.off_threshold_by_native_leg)
    states = np.zeros((len(times), 4), dtype=bool)
    events: list[dict[str, Any]] = []
    for leg_index, leg in enumerate(NATIVE_FOOT_ORDER):
        current = bool(forces[0, leg_index] >= 0.5 * (on[leg_index] + off[leg_index]))
        candidate: bool | None = None
        candidate_start_index: int | None = None
        states[0, leg_index] = current
        for sample_index in range(1, len(times)):
            value = forces[sample_index, leg_index]
            triggered_target: bool | None = None
            if not current and value >= on[leg_index]:
                triggered_target = True
            elif current and value <= off[leg_index]:
                triggered_target = False
            if triggered_target is None:
                candidate = None
                candidate_start_index = None
            else:
                if candidate != triggered_target:
                    candidate = triggered_target
                    candidate_start_index = sample_index
                assert candidate_start_index is not None
                elapsed = times[sample_index] - times[candidate_start_index]
                if elapsed + NUMERICAL_TOLERANCE >= config.minimum_dwell_seconds:
                    previous = current
                    current = triggered_target
                    events.append({
                        "row_type": "transition",
                        "native_leg_index": leg_index,
                        "leg": leg,
                        "sample_index": sample_index,
                        "threshold_crossing_start_index": candidate_start_index,
                        "threshold_crossing_start_time_seconds": float(
                            times[candidate_start_index]
                        ),
                        "event_time_seconds": float(times[sample_index]),
                        "debounce_elapsed_seconds": float(elapsed),
                        "from_contact": int(previous),
                        "to_contact": int(current),
                        "force_at_event": float(value),
                    })
                    candidate = None
                    candidate_start_index = None
            states[sample_index, leg_index] = current
    return states, events


def frozen_force_contact_states(
    records: Sequence[HartleyInputRecord],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Apply the frozen per-leg force thresholds with both dwell requirements."""

    arrays = _record_arrays(records)
    config = ContactDetectorConfig(
        on_threshold_by_native_leg=FROZEN_CONTACT_ON_THRESHOLDS,
        off_threshold_by_native_leg=FROZEN_CONTACT_OFF_THRESHOLDS,
        minimum_dwell_seconds=FROZEN_CONTACT_DWELL_SECONDS,
        minimum_dwell_samples_source=FROZEN_CONTACT_DWELL_SAMPLES,
    )
    return force_hysteresis_contacts(
        arrays["time"], arrays["foot_force"], config
    )


def _project_psd_with_floor(
    matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    symmetric = 0.5 * (matrix + matrix.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    projected_eigenvalues = np.maximum(eigenvalues, 0.0)
    floored_eigenvalues = np.maximum(
        projected_eigenvalues, FK_COVARIANCE_EIGENVALUE_FLOOR_M2
    )
    final = eigenvectors @ np.diag(floored_eigenvalues) @ eigenvectors.T
    final = 0.5 * (final + final.T)
    return symmetric, eigenvalues, floored_eigenvalues, final


def compute_fk_proxy_covariance(
    records: Sequence[HartleyInputRecord],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compute the frozen robust input-only translation covariance policy."""

    arrays = _record_arrays(records)
    times = arrays["time"]
    positions = arrays["foot_position_body"]
    velocities = arrays["foot_speed_body"]
    gyro_norm = np.linalg.norm(arrays["gyroscope"], axis=1)
    accel_error = np.abs(np.linalg.norm(arrays["accelerometer"], axis=1) - 9.81)
    contacts, contact_events = frozen_force_contact_states(records)
    per_leg: dict[str, dict[str, Any]] = {}
    per_leg_final: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []
    axes = ("x", "y", "z")
    for leg_index, leg in enumerate(NATIVE_FOOT_ORDER):
        residuals: list[np.ndarray] = []
        rejection_counts = {
            "pair_count": max(0, len(records) - 1),
            "both_contact": 0,
            "gyro_gate": 0,
            "accel_gate": 0,
            "positive_finite_dt": 0,
            "finite_position_velocity": 0,
            "eligible": 0,
        }
        for sample_index in range(1, len(records)):
            both_contact = bool(
                contacts[sample_index - 1, leg_index]
                and contacts[sample_index, leg_index]
            )
            if both_contact:
                rejection_counts["both_contact"] += 1
            gyro_ok = bool(
                gyro_norm[sample_index - 1] < 0.05
                and gyro_norm[sample_index] < 0.05
            )
            if gyro_ok:
                rejection_counts["gyro_gate"] += 1
            accel_ok = bool(
                accel_error[sample_index - 1] <= 0.5
                and accel_error[sample_index] <= 0.5
            )
            if accel_ok:
                rejection_counts["accel_gate"] += 1
            dt = float(times[sample_index] - times[sample_index - 1])
            dt_ok = bool(math.isfinite(float(dt)) and dt > 0.0)
            if dt_ok:
                rejection_counts["positive_finite_dt"] += 1
            values = np.concatenate((
                positions[sample_index - 1, leg_index],
                positions[sample_index, leg_index],
                velocities[sample_index - 1, leg_index],
                velocities[sample_index, leg_index],
            ))
            finite_pv = bool(np.all(np.isfinite(values)))
            if finite_pv:
                rejection_counts["finite_position_velocity"] += 1
            if not (both_contact and gyro_ok and accel_ok and dt_ok and finite_pv):
                continue
            residual = (
                positions[sample_index, leg_index]
                - positions[sample_index - 1, leg_index]
                - 0.5
                * (
                    velocities[sample_index, leg_index]
                    + velocities[sample_index - 1, leg_index]
                )
                * dt
            )
            residuals.append(residual)
        residual_array = np.asarray(residuals, dtype=float).reshape((-1, 3))
        rejection_counts["eligible"] = len(residual_array)
        all_finite = bool(np.all(np.isfinite(residual_array)))
        if len(residual_array):
            centers = np.median(residual_array, axis=0)
            lower = np.percentile(residual_array, 0.5, axis=0, method="linear")
            upper = np.percentile(residual_array, 99.5, axis=0, method="linear")
            winsorized = np.clip(residual_array, lower, upper)
        else:
            centers = np.zeros(3, dtype=float)
            lower = np.zeros(3, dtype=float)
            upper = np.zeros(3, dtype=float)
            winsorized = residual_array
        if len(winsorized) >= 2:
            centered = winsorized - centers
            raw_covariance = centered.T @ centered / (len(winsorized) - 1)
        else:
            raw_covariance = np.zeros((3, 3), dtype=float)
        symmetric, raw_eigenvalues, final_eigenvalues, final_covariance = (
            _project_psd_with_floor(raw_covariance)
        )
        raw_condition_value = float(np.linalg.cond(symmetric, p=2))
        raw_condition = (
            raw_condition_value if math.isfinite(raw_condition_value) else None
        )
        symmetry_error = float(
            np.linalg.norm(final_covariance - final_covariance.T, ord=np.inf)
        )
        condition = float(np.linalg.cond(final_covariance, p=2))
        gate = {
            "residual_count_at_least_100": (
                len(residual_array) >= FK_COVARIANCE_MIN_RESIDUALS
            ),
            "all_residuals_finite": all_finite,
            "pre_floor_condition_at_most_1e8": (
                raw_condition is not None
                and raw_condition <= FK_COVARIANCE_MAX_CONDITION
            ),
            "final_condition_at_most_1e8": (
                condition <= FK_COVARIANCE_MAX_CONDITION
            ),
            "symmetry_error_at_most_1e_minus_12": (
                symmetry_error <= FK_COVARIANCE_MAX_SYMMETRY_ERROR
            ),
        }
        passed = all(gate.values())
        detail: dict[str, Any] = {
            "native_leg_index": leg_index,
            "leg": leg,
            "eligibility_counts": rejection_counts,
            "residual_count": len(residual_array),
            "component_center_m": centers.tolist(),
            "winsor_quantile_0p5_m": lower.tolist(),
            "winsor_quantile_99p5_m": upper.tolist(),
            "winsor_method": "linear",
            "covariance_center": "componentwise_raw_residual_median",
            "covariance_denominator": "n_minus_1",
            "raw_covariance_m2": raw_covariance.tolist(),
            "symmetric_covariance_m2": symmetric.tolist(),
            "raw_symmetric_eigenvalues_m2": raw_eigenvalues.tolist(),
            "raw_symmetric_condition_2norm": raw_condition,
            "final_eigenvalues_m2": final_eigenvalues.tolist(),
            "final_covariance_m2": final_covariance.tolist(),
            "final_condition_2norm": condition,
            "final_symmetry_error_inf": symmetry_error,
            "well_conditioned_gate": gate,
            "well_conditioned": passed,
        }
        per_leg[leg] = detail
        per_leg_final.append(final_covariance)
        for axis_index, axis in enumerate(axes):
            rows.append({
                "native_leg_index": leg_index,
                "leg": leg,
                "row_type": "component",
                "axis": axis,
                "residual_count": len(residual_array),
                "center_m": float(centers[axis_index]),
                "winsor_q0p5_m": float(lower[axis_index]),
                "winsor_q99p5_m": float(upper[axis_index]),
                "raw_covariance_x_m2": float(raw_covariance[axis_index, 0]),
                "raw_covariance_y_m2": float(raw_covariance[axis_index, 1]),
                "raw_covariance_z_m2": float(raw_covariance[axis_index, 2]),
                "symmetric_covariance_x_m2": float(symmetric[axis_index, 0]),
                "symmetric_covariance_y_m2": float(symmetric[axis_index, 1]),
                "symmetric_covariance_z_m2": float(symmetric[axis_index, 2]),
                "raw_symmetric_eigenvalue_m2": float(raw_eigenvalues[axis_index]),
                "final_eigenvalue_m2": float(final_eigenvalues[axis_index]),
                "pre_fallback_final_covariance_x_m2": float(
                    final_covariance[axis_index, 0]
                ),
                "pre_fallback_final_covariance_y_m2": float(
                    final_covariance[axis_index, 1]
                ),
                "pre_fallback_final_covariance_z_m2": float(
                    final_covariance[axis_index, 2]
                ),
                "selected_covariance_x_m2": float(final_covariance[axis_index, 0]),
                "selected_covariance_y_m2": float(final_covariance[axis_index, 1]),
                "selected_covariance_z_m2": float(final_covariance[axis_index, 2]),
                "raw_symmetric_condition_2norm": raw_condition,
                "condition_2norm": condition,
                "well_conditioned": passed,
                "fallback_applied": "",
            })
    triggering_legs = [
        leg for leg in NATIVE_FOOT_ORDER if not per_leg[leg]["well_conditioned"]
    ]
    fallback_applied = bool(triggering_legs)
    fallback_covariance: np.ndarray | None = None
    fallback_elementwise_median: np.ndarray | None = None
    fallback_symmetric: np.ndarray | None = None
    fallback_raw_eigenvalues: np.ndarray | None = None
    fallback_eigenvalues: np.ndarray | None = None
    fallback_condition: float | None = None
    fallback_symmetry_error: float | None = None
    if fallback_applied:
        fallback_elementwise_median = np.median(
            np.stack(per_leg_final, axis=0), axis=0
        )
        (
            fallback_symmetric,
            fallback_raw_eigenvalues,
            fallback_eigenvalues,
            fallback_covariance,
        ) = _project_psd_with_floor(fallback_elementwise_median)
        fallback_condition = float(np.linalg.cond(fallback_covariance, p=2))
        fallback_symmetry_error = float(
            np.linalg.norm(
                fallback_covariance - fallback_covariance.T, ord=np.inf
            )
        )
        for leg in NATIVE_FOOT_ORDER:
            per_leg[leg]["selected_covariance_m2"] = fallback_covariance.tolist()
            per_leg[leg]["fallback_applied"] = True
        for row in rows:
            axis_index = axes.index(str(row["axis"]))
            row["selected_covariance_x_m2"] = float(
                fallback_covariance[axis_index, 0]
            )
            row["selected_covariance_y_m2"] = float(
                fallback_covariance[axis_index, 1]
            )
            row["selected_covariance_z_m2"] = float(
                fallback_covariance[axis_index, 2]
            )
            row["fallback_applied"] = True
    else:
        for leg in NATIVE_FOOT_ORDER:
            per_leg[leg]["selected_covariance_m2"] = per_leg[leg][
                "final_covariance_m2"
            ]
            per_leg[leg]["fallback_applied"] = False
        for row in rows:
            row["fallback_applied"] = False
    all_legs_well_conditioned = not triggering_legs
    fallback_valid = bool(
        fallback_applied
        and fallback_covariance is not None
        and np.all(np.isfinite(fallback_covariance))
        and fallback_condition is not None
        and fallback_condition <= FK_COVARIANCE_MAX_CONDITION
        and fallback_symmetry_error is not None
        and fallback_symmetry_error <= FK_COVARIANCE_MAX_SYMMETRY_ERROR
    )
    filter_eligible = all_legs_well_conditioned or fallback_valid
    floor_dominates_all_legs = all(
        max(per_leg[leg]["raw_symmetric_eigenvalues_m2"])
        < FK_COVARIANCE_EIGENVALUE_FLOOR_M2
        for leg in NATIVE_FOOT_ORDER
    )
    summary = {
        "schema_version": "hartley.fk_proxy_covariance.v1",
        "status": "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE",
        "source_role": "INPUT_ONLY_FK_PROXY_COVARIANCE_AUDIT",
        "foot_speed_role": "DIAGNOSTIC_ONLY",
        "foot_speed_online_allowed": False,
        "foot_speed_changes_contact_threshold_or_state": False,
        "foot_speed_offline_fk_covariance_residual_used": True,
        "reference_tuned": False,
        "output_metric_tuned": False,
        "contact_policy": {
            "decision_signal": "foot_force_only",
            "native_foot_order": list(NATIVE_FOOT_ORDER),
            "off_thresholds": list(FROZEN_CONTACT_OFF_THRESHOLDS),
            "on_thresholds": list(FROZEN_CONTACT_ON_THRESHOLDS),
            "minimum_dwell_samples": FROZEN_CONTACT_DWELL_SAMPLES,
            "minimum_dwell_seconds": FROZEN_CONTACT_DWELL_SECONDS,
            "transition_event_count": len(contact_events),
        },
        "eligibility": {
            "both_k_minus_1_and_k_contact": True,
            "gyro_norm_strictly_below_radps": 0.05,
            "absolute_accel_norm_minus_9p81_at_most_mps2": 0.5,
            "positive_finite_dt_required": True,
            "finite_position_velocity_required": True,
        },
        "winsor_quantiles": [0.005, 0.995],
        "winsor_method": "linear",
        "eigenvalue_floor_m2": FK_COVARIANCE_EIGENVALUE_FLOOR_M2,
        "primary_scale": FK_COVARIANCE_PRIMARY_SCALE,
        "sensitivity_scales": list(FK_COVARIANCE_SENSITIVITY_SCALES),
        "well_conditioned_gate": {
            "minimum_residual_count": FK_COVARIANCE_MIN_RESIDUALS,
            "maximum_pre_floor_condition_2norm": FK_COVARIANCE_MAX_CONDITION,
            "maximum_final_condition_2norm": FK_COVARIANCE_MAX_CONDITION,
            "maximum_symmetry_error": FK_COVARIANCE_MAX_SYMMETRY_ERROR,
        },
        "all_legs_well_conditioned": all_legs_well_conditioned,
        "valid_recorded_median_fallback": fallback_valid,
        "filter_eligible": filter_eligible,
        "floor_dominates_all_raw_leg_covariances": floor_dominates_all_legs,
        "floor_dominance_statement": (
            "ALL_RAW_MAX_EIGENVALUES_BELOW_1E-8_M2;FINAL_FLOOR_DOMINATES"
            if floor_dominates_all_legs else
            "RAW_EIGENVALUE_AT_OR_ABOVE_1E-8_M2_PRESENT"
        ),
        "per_leg": per_leg,
        "fallback_applied": fallback_applied,
        "fallback_triggering_legs": triggering_legs,
        "fallback_rule": "elementwise_median_then_symmetrize_project_floor",
        "fallback_elementwise_median_m2": (
            fallback_elementwise_median.tolist()
            if fallback_elementwise_median is not None else None
        ),
        "fallback_symmetric_m2": (
            fallback_symmetric.tolist() if fallback_symmetric is not None else None
        ),
        "fallback_raw_eigenvalues_m2": (
            fallback_raw_eigenvalues.tolist()
            if fallback_raw_eigenvalues is not None else None
        ),
        "fallback_covariance_m2": (
            fallback_covariance.tolist() if fallback_covariance is not None else None
        ),
        "fallback_final_eigenvalues_m2": (
            fallback_eigenvalues.tolist() if fallback_eigenvalues is not None else None
        ),
        "fallback_condition_2norm": fallback_condition,
        "fallback_symmetry_error_inf": fallback_symmetry_error,
    }
    return rows, summary


def _state_segments(
    times: np.ndarray,
    states: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for leg_index, leg in enumerate(NATIVE_FOOT_ORDER):
        start = 0
        for stop in range(1, len(times) + 1):
            boundary = stop == len(times) or states[stop, leg_index] != states[start, leg_index]
            if not boundary:
                continue
            rows.append({
                "row_type": "dwell",
                "native_leg_index": leg_index,
                "leg": leg,
                "sample_index": "",
                "threshold_crossing_start_index": "",
                "threshold_crossing_start_time_seconds": "",
                "event_time_seconds": "",
                "debounce_elapsed_seconds": "",
                "from_contact": "",
                "to_contact": int(states[start, leg_index]),
                "force_at_event": "",
                "dwell_start_time_seconds": float(times[start]),
                "dwell_end_time_seconds": float(times[stop - 1]),
                "dwell_duration_seconds": float(times[stop - 1] - times[start]),
                "dwell_sample_count": stop - start,
            })
            start = stop
    return rows


def contact_diagnostic_audit(
    records: Sequence[HartleyInputRecord],
    states: np.ndarray,
    transition_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    arrays = _record_arrays(records)
    times = arrays["time"]
    speed_norm = np.linalg.norm(arrays["foot_speed_body"], axis=2)
    if states.shape != (len(records), 4):
        raise RequiredFieldError("contact diagnostic state shape is not Nx4")
    dwell_segments = _state_segments(times, states)
    per_leg: dict[str, Any] = {}
    for leg_index, leg in enumerate(NATIVE_FOOT_ORDER):
        contact_mask = states[:, leg_index]
        no_contact_mask = ~contact_mask
        speed_by_state: dict[str, Any] = {}
        for label, mask in (("contact", contact_mask), ("no_contact", no_contact_mask)):
            speed_by_state[label] = (
                _numeric_summary(speed_norm[mask, leg_index]) if np.any(mask) else None
            )
        dwell_rows = [row for row in dwell_segments if row["native_leg_index"] == leg_index]
        contact_dwell_values = np.asarray([
            row["dwell_duration_seconds"] for row in dwell_rows if row["to_contact"] == 1
        ])
        no_contact_dwell_values = np.asarray([
            row["dwell_duration_seconds"] for row in dwell_rows if row["to_contact"] == 0
        ])
        leg_events = [
            row for row in transition_events if row["native_leg_index"] == leg_index
        ]
        on_transition_count = sum(int(row["to_contact"] == 1) for row in leg_events)
        off_transition_count = sum(int(row["to_contact"] == 0) for row in leg_events)
        contact_fraction = float(np.mean(contact_mask))
        no_contact_fraction = float(np.mean(no_contact_mask))
        contact_speed = speed_by_state["contact"]
        no_contact_speed = speed_by_state["no_contact"]
        criteria = {
            "contact_fraction_at_least_0p01": (
                contact_fraction >= CONTACT_STABILITY_MIN_STATE_FRACTION
            ),
            "no_contact_fraction_at_least_0p01": (
                no_contact_fraction >= CONTACT_STABILITY_MIN_STATE_FRACTION
            ),
            "at_least_one_on_transition": on_transition_count >= 1,
            "at_least_one_off_transition": off_transition_count >= 1,
            "transition_count_at_least_two": len(leg_events) >= 2,
            "contact_dwell_distribution_nonempty": bool(len(contact_dwell_values)),
            "no_contact_dwell_distribution_nonempty": bool(len(no_contact_dwell_values)),
        }
        speed_ordering_diagnostic = (
            contact_speed is not None
            and no_contact_speed is not None
            and float(no_contact_speed["p50"]) > float(contact_speed["p50"])
        )
        per_leg[leg] = {
            "contact_fraction": contact_fraction,
            "no_contact_fraction": no_contact_fraction,
            "transition_count": len(leg_events),
            "on_transition_count": on_transition_count,
            "off_transition_count": off_transition_count,
            "contact_dwell_seconds": (
                _numeric_summary(contact_dwell_values) if len(contact_dwell_values) else None
            ),
            "no_contact_dwell_seconds": (
                _numeric_summary(no_contact_dwell_values) if len(no_contact_dwell_values) else None
            ),
            "foot_speed_norm_diagnostic_by_force_state": speed_by_state,
            "diagnostic_no_contact_median_speed_greater_than_contact": (
                speed_ordering_diagnostic
            ),
            "stability_criteria": criteria,
            "contact_input_stable": all(criteria.values()),
        }
    gait_cross_tab: dict[str, Any] = {}
    for gait in sorted({row.gait_type for row in records}):
        mask = np.asarray([row.gait_type == gait for row in records])
        gait_cross_tab[gait] = {
            leg: {
                "sample_count": int(np.sum(mask)),
                "force_contact_fraction": float(np.mean(states[mask, leg_index])),
            }
            for leg_index, leg in enumerate(NATIVE_FOOT_ORDER)
        }
    contact_input_stable = all(
        per_leg[leg]["contact_input_stable"] for leg in NATIVE_FOOT_ORDER
    )
    return {
        "schema_version": "hartley.contact_input_audit.v1",
        "decision_source": "foot_force_only",
        "foot_speed_role": "DIAGNOSTIC_ONLY",
        "foot_speed_online_allowed": False,
        "foot_speed_changes_threshold_or_state_classification": False,
        "gait_type_role": "input_audit_grouping_only",
        "stability_rule": {
            "minimum_fraction_per_state_per_leg": CONTACT_STABILITY_MIN_STATE_FRACTION,
            "minimum_transition_count_per_leg": 2,
            "requires_on_and_off_transition_per_leg": True,
            "requires_both_dwell_distributions_per_leg": True,
            "diagnostic_speed_ordering_not_a_gate": (
                "median_no_contact_greater_than_median_contact"
            ),
        },
        "contact_input_stable": contact_input_stable,
        "per_leg": per_leg,
        "gait_type_cross_tab": gait_cross_tab,
        "mode_counts": {
            key: sum(row.mode == key for row in records)
            for key in sorted({row.mode for row in records if row.mode is not None})
        },
    }


def fk_proxy_audit(
    records: Sequence[HartleyInputRecord],
    *,
    contact_states: np.ndarray | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arrays = _record_arrays(records)
    positions = arrays["foot_position_body"]
    speeds = arrays["foot_speed_body"]
    times = arrays["time"]
    axis_names = ("x", "y", "z")
    rows: list[dict[str, Any]] = []
    discontinuity: dict[str, Any] = {}
    for leg_index, leg in enumerate(NATIVE_FOOT_ORDER):
        steps = np.linalg.norm(np.diff(positions[:, leg_index, :], axis=0), axis=1)
        if len(steps):
            median = float(np.median(steps))
            mad = float(np.median(np.abs(steps - median)))
            threshold = median + 10.0 * 1.4826 * mad
            if threshold <= NUMERICAL_TOLERANCE:
                threshold = NUMERICAL_TOLERANCE
            count = int(np.sum(steps > threshold))
            maximum = float(np.max(steps))
        else:
            threshold = NUMERICAL_TOLERANCE
            count = 0
            maximum = 0.0
        discontinuity[leg] = {
            "input_only_step_norm_threshold_m": threshold,
            "candidate_discontinuity_count": count,
            "maximum_position_step_m": maximum,
        }
        for axis_index, axis in enumerate(axis_names):
            position_summary = _numeric_summary(positions[:, leg_index, axis_index])
            speed_summary = _numeric_summary(speeds[:, leg_index, axis_index])
            row: dict[str, Any] = {
                "native_leg_index": leg_index,
                "leg": leg,
                "axis": axis,
                **{f"position_{key}": value for key, value in position_summary.items()},
                **{f"speed_{key}": value for key, value in speed_summary.items()},
                "force_contact_position_std": "",
                "force_no_contact_position_std": "",
            }
            if contact_states is not None:
                contact = contact_states[:, leg_index]
                if np.any(contact):
                    row["force_contact_position_std"] = float(
                        np.std(positions[contact, leg_index, axis_index])
                    )
                if np.any(~contact):
                    row["force_no_contact_position_std"] = float(
                        np.std(positions[~contact, leg_index, axis_index])
                    )
            rows.append(row)

    medians = np.median(positions, axis=0)
    geometry_checks = {
        "front_x_positive": bool(medians[0, 0] > 0.0 and medians[1, 0] > 0.0),
        "rear_x_negative": bool(medians[2, 0] < 0.0 and medians[3, 0] < 0.0),
        "right_y_negative": bool(medians[0, 1] < 0.0 and medians[2, 1] < 0.0),
        "left_y_positive": bool(medians[1, 1] > 0.0 and medians[3, 1] > 0.0),
    }
    report = {
        "schema_version": "hartley.by2_fk_proxy_audit.v1",
        "adapter_identity": "GO2_HIGH_LEVEL_FK_LIKE_PROXY",
        "raw_joint_encoder_urdf_fk": False,
        "native_foot_order": list(NATIVE_FOOT_ORDER),
        "canonical_foot_order": list(CANONICAL_FOOT_ORDER),
        "native_to_canonical_mapping": list(NATIVE_TO_CANONICAL),
        "finite_position_rate": float(np.mean(np.isfinite(positions))),
        "finite_speed_rate": float(np.mean(np.isfinite(speeds))),
        "time_alignment": {
            "contract": "same_message_timestamp_as_imu",
            "position_to_imu_max_offset_seconds": 0.0,
            "speed_to_imu_max_offset_seconds": 0.0,
            "message_count": len(times),
        },
        "median_position_body_by_native_leg_m": {
            leg: medians[index].tolist() for index, leg in enumerate(NATIVE_FOOT_ORDER)
        },
        "native_flu_geometry_checks": geometry_checks,
        "native_flu_geometry_sanity_pass": all(geometry_checks.values()),
        "position_discontinuity_audit": discontinuity,
        "kinematic_pose_rotation_role": "identity_placeholder_unused_by_point_contact",
        "translation_covariance_status": "TO_BE_FROZEN_FROM_INPUT_ONLY_ANALYSIS",
        "orientation_covariance_status": "NONINFORMATIVE_PLACEHOLDER_NOT_USED",
    }
    return rows, report


def build_hartley_input_audit(
    records: Sequence[HartleyInputRecord],
    *,
    expected_complete_record_count: int | None = EXPECTED_BY2_USABLE_RECORD_COUNT,
    minimum_dwell_samples: int = DEFAULT_MINIMUM_DWELL_SAMPLES,
    scan_result: CompleteRecordScanResult | None = None,
) -> dict[str, Any]:
    arrays = _record_arrays(records)
    timing = timing_audit(records)
    detector, proposal = derive_force_contact_proposal(
        records, minimum_dwell_samples=minimum_dwell_samples
    )
    states: np.ndarray | None = None
    transitions: list[dict[str, Any]] = []
    contact_report: dict[str, Any] = {
        "schema_version": "hartley.contact_input_audit.v1",
        "status": "INPUT_NOT_IDENTIFIABLE",
        "contact_input_stable": False,
    }
    frozen_contact_policy_matches_rederived = bool(
        detector is not None
        and tuple(
            round(float(proposal["per_leg"][leg]["off_threshold"]), 1)
            for leg in NATIVE_FOOT_ORDER
        ) == FROZEN_CONTACT_OFF_THRESHOLDS
        and tuple(
            round(float(proposal["per_leg"][leg]["on_threshold"]), 1)
            for leg in NATIVE_FOOT_ORDER
        ) == FROZEN_CONTACT_ON_THRESHOLDS
        and proposal["minimum_dwell_samples_source"] == FROZEN_CONTACT_DWELL_SAMPLES
        and proposal["minimum_dwell_seconds"] == FROZEN_CONTACT_DWELL_SECONDS
    )
    proposal["frozen_policy_exact_match"] = frozen_contact_policy_matches_rederived
    proposal["frozen_policy_threshold_comparison"] = (
        "ROUND_HALF_EVEN_TO_ONE_DECIMAL_THEN_EXACT_EQUAL"
    )
    proposal["frozen_policy"] = {
        "off_thresholds": list(FROZEN_CONTACT_OFF_THRESHOLDS),
        "on_thresholds": list(FROZEN_CONTACT_ON_THRESHOLDS),
        "minimum_dwell_samples": FROZEN_CONTACT_DWELL_SAMPLES,
        "minimum_dwell_seconds": FROZEN_CONTACT_DWELL_SECONDS,
    }
    if scan_result is not None and frozen_contact_policy_matches_rederived:
        states, transitions = frozen_force_contact_states(records)
        contact_report = contact_diagnostic_audit(records, states, transitions)
        contact_report["status"] = "FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY"
        contact_report["rederived_policy_exact_match"] = True
    elif scan_result is not None:
        contact_report["status"] = "FROZEN_BY2_CONTACT_POLICY_REDERIVATION_MISMATCH"
        contact_report["rederived_policy_exact_match"] = False
    elif detector is not None:
        states, transitions = force_hysteresis_contacts(
            arrays["time"], arrays["foot_force"], detector
        )
        contact_report = contact_diagnostic_audit(records, states, transitions)
        contact_report["status"] = (
            "INPUT_ONLY_CONTACT_CANDIDATE_STABLE"
            if contact_report["contact_input_stable"]
            else "INPUT_ONLY_CONTACT_CANDIDATE_NOT_STABLE"
        )
    fk_rows, fk_report = fk_proxy_audit(records, contact_states=states)
    covariance_rows, covariance_report = compute_fk_proxy_covariance(records)
    fk_report["translation_covariance_status"] = (
        "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE"
    )
    fk_report["translation_covariance_filter_eligible"] = covariance_report[
        "filter_eligible"
    ]
    fk_report["translation_covariance_summary"] = covariance_report
    force_rows = _distribution_rows(arrays["foot_force"], quantity="foot_force")
    speed_rows = _distribution_rows(
        np.linalg.norm(arrays["foot_speed_body"], axis=2),
        quantity="foot_speed_body_norm",
    )
    transition_rows = list(transitions)
    if states is not None:
        transition_rows.extend(_state_segments(arrays["time"], states))
    if scan_result is not None:
        if tuple(records) != scan_result.records:
            raise HartleyH0H2Error("audit records differ from the accepted policy prefix")
        timing.update({
            "first_timestamp_ns": scan_result.first_complete_timestamp_ns,
            "last_timestamp_ns": scan_result.last_complete_timestamp_ns,
            "duration_ns": scan_result.duration_ns,
            "duration_seconds": scan_result.duration_seconds,
            "float_timestamp_subtraction_authoritative": False,
        })
        prefix_manifest = complete_record_prefix_manifest(scan_result)
        trailing_ledger = trailing_record_ledger(scan_result)
    else:
        prefix_manifest = {
            "schema_version": "hartley.by2_complete_record_prefix_manifest.v1",
            "policy_id": None,
            "data_mode": "synthetic",
            "synthetic_data_used": True,
            "semisynthetic_data_used": False,
            "policy_applied": False,
            "complete_record_count": len(records),
            "expected_complete_record_count": expected_complete_record_count,
            "complete_record_count_matches_policy": (
                expected_complete_record_count is None
                or len(records) == expected_complete_record_count
            ),
        }
        trailing_ledger = {
            "schema_version": "hartley.by2_trailing_record_ledger.v1",
            "policy_id": None,
            "data_mode": "synthetic",
            "synthetic_data_used": True,
            "policy_applied": False,
            "partial_record_contributes_projection_row": False,
            "foot_speed_role": "DIAGNOSTIC_ONLY",
            "foot_speed_online_allowed": False,
            "foot_speed_changes_threshold_or_state": False,
        }
    real_prefix = scan_result is not None
    data_identity = (
        "REAL_BY2_COMPLETE_RECORD_PREFIX_63277"
        if real_prefix else "SYNTHETIC_IN_MEMORY_HARTLEY_AUDIT"
    )
    data_status = (
        "REAL_BY2_COMPLETE_RECORD_PREFIX"
        if real_prefix else "SYNTHETIC_TEST_ONLY"
    )
    return {
        "summary": {
            "schema_version": "hartley.h0_h2.by2_input_audit.v1",
            "method_id": "LSE01_HARTLEY_CONTACT_AIDED_INEKF",
            "algorithm_core": "FAITHFUL_ALGORITHM_REPRODUCTION",
            "by2_adaptation": "WITH_DECLARED_GO2_HIGH_LEVEL_FK_PROXY",
            "data_mode": "real_by2_raw" if scan_result is not None else "synthetic",
            "synthetic_data_used": scan_result is None,
            "semisynthetic_data_used": False,
            "complete_record_policy_id": (
                scan_result.policy.policy_id if scan_result is not None else None
            ),
            "complete_record_policy_applied": scan_result is not None,
            "timing": timing,
            "data_identity": data_identity,
            "data_status": data_status,
            "raw_source_complete": False if real_prefix else None,
            "complete_record_prefix_filter_eligible": (
                bool(prefix_manifest.get("complete_record_prefix_filter_eligible"))
                if real_prefix else True
            ),
            "expected_complete_record_count": expected_complete_record_count,
            "complete_record_count": len(records),
            "complete_record_count_matches_policy": (
                expected_complete_record_count is None
                or len(records) == expected_complete_record_count
            ),
            "raw_source_sha256": scan_result.raw_sha256 if real_prefix else None,
            "complete_prefix_sha256": scan_result.prefix_sha256 if real_prefix else None,
            "trailing_incomplete_record_count": (
                scan_result.incomplete_record_count if real_prefix else 0
            ),
            "no_imputation": True,
            "no_interpolation": True,
            "raw_source_mutated": False,
            "foot_speed_role": "DIAGNOSTIC_ONLY",
            "foot_speed_online_allowed": False,
            "foot_speed_changes_threshold_or_state": False,
            "projected_shapes": {
                "gyroscope": list(arrays["gyroscope"].shape),
                "accelerometer": list(arrays["accelerometer"].shape),
                "foot_force": list(arrays["foot_force"].shape),
                "foot_position_body": list(arrays["foot_position_body"].shape),
                "foot_speed_body": list(arrays["foot_speed_body"].shape),
            },
            "gait_type_counts": {
                key: sum(row.gait_type == key for row in records)
                for key in sorted({row.gait_type for row in records})
            },
            "mode_present_count": sum(row.mode is not None for row in records),
            "contact_input_identifiable": detector is not None,
            "contact_input_stable": bool(contact_report["contact_input_stable"]),
            "frozen_contact_policy_matches_rederived": (
                frozen_contact_policy_matches_rederived if real_prefix else None
            ),
            "contact_policy_status": contact_report["status"],
            "fk_covariance_status": covariance_report["status"],
            "fk_covariance_filter_eligible": covariance_report["filter_eligible"],
            "fk_native_geometry_sanity_pass": bool(
                fk_report["native_flu_geometry_sanity_pass"]
            ),
            "external_reference_open_count": 0,
            "filter_run_count": 0,
            "filter_run_executed": False,
            "real_by2_filter_run": False,
            "navigation_output_write_count": 0,
            "navigation_output_written": False,
        },
        "contact_threshold_proposal": proposal,
        "contact_report": contact_report,
        "force_distribution_rows": force_rows,
        "speed_distribution_rows": speed_rows,
        "transition_rows": transition_rows,
        "fk_rows": fk_rows,
        "fk_report": fk_report,
        "fk_covariance_rows": covariance_rows,
        "fk_covariance_report": covariance_report,
        "record_prefix_manifest": prefix_manifest,
        "trailing_record_ledger": trailing_ledger,
    }


def _write_new_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    _write_new_text(path, json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _write_new_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise HartleyH0H2Error(f"refusing empty CSV output: {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def hartley_audit_prepublication_blocker(
    audit: Mapping[str, Any],
) -> dict[str, str] | None:
    """Evaluate every input gate before a canonical audit directory exists."""

    summary = audit.get("summary")
    fk_report = audit.get("fk_report")
    covariance = audit.get("fk_covariance_report")
    if (
        not isinstance(summary, Mapping)
        or not isinstance(fk_report, Mapping)
        or not isinstance(covariance, Mapping)
    ):
        return {
            "terminal_status": "BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING",
            "error": "audit payload omits summary, FK report, or covariance report",
        }
    if summary.get("complete_record_count_matches_policy") is not True:
        return {
            "terminal_status": "BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING",
            "error": "complete-record count does not match its frozen policy",
        }
    real_prefix = summary.get("data_mode") == "real_by2_raw"
    if real_prefix and not all((
        summary.get("data_identity") == "REAL_BY2_COMPLETE_RECORD_PREFIX_63277",
        summary.get("data_status") == "REAL_BY2_COMPLETE_RECORD_PREFIX",
        summary.get("raw_source_complete") is False,
        summary.get("complete_record_prefix_filter_eligible") is True,
        summary.get("no_imputation") is True,
        summary.get("no_interpolation") is True,
        summary.get("raw_source_mutated") is False,
        summary.get("complete_record_policy_applied") is True,
    )):
        return {
            "terminal_status": "BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING",
            "error": "real BY2 complete-prefix identity or immutability gate failed",
        }
    if real_prefix and summary.get("frozen_contact_policy_matches_rederived") is not True:
        return {
            "terminal_status": "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE",
            "error": "rederived contact thresholds/dwell differ from the frozen policy",
        }
    if real_prefix and summary.get("contact_policy_status") != (
        "FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY"
    ):
        return {
            "terminal_status": "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE",
            "error": "final contact rows do not use the frozen BY2 input-only policy",
        }
    if summary.get("contact_input_identifiable") is not True:
        return {
            "terminal_status": "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE",
            "error": "per-leg force modes are not identifiable",
        }
    if summary.get("contact_input_stable") is not True:
        return {
            "terminal_status": "BLOCKED_LSE01_CONTACT_INPUT_NOT_IDENTIFIABLE",
            "error": "frozen per-leg temporal contact-stability criteria failed",
        }
    if (
        covariance.get("status")
        != "FROZEN_BY2_INPUT_ONLY_FK_PROXY_COVARIANCE"
        or covariance.get("filter_eligible") is not True
        or not (
            covariance.get("all_legs_well_conditioned") is True
            or covariance.get("valid_recorded_median_fallback") is True
        )
    ):
        return {
            "terminal_status": "BLOCKED_LSE01_BY2_REQUIRED_FIELD_MISSING",
            "error": "FK proxy covariance lacks a valid per-leg or median-fallback gate",
        }
    if fk_report.get("native_flu_geometry_sanity_pass") is not True:
        return {
            "terminal_status": "BLOCKED_LSE01_FOOT_ORDER_CONTRACT_UNRESOLVED",
            "error": "native foot geometry sign sanity failed",
        }
    return None


_AUDIT_OUTPUT_NAMES = {
    "BY2_PROJECTION_AUDIT_SUMMARY.json",
    "BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json",
    "BY2_TRAILING_RECORD_LEDGER.json",
    "FK_PROXY_AUDIT.csv",
    "FK_PROXY_AUDIT.json",
    "FK_PROXY_COVARIANCE_ESTIMATION.csv",
    "FK_PROXY_COVARIANCE_SUMMARY.json",
    "CONTACT_FORCE_DISTRIBUTIONS.csv",
    "CONTACT_SPEED_DISTRIBUTIONS.csv",
    "CONTACT_TRANSITION_AUDIT.csv",
    "CONTACT_THRESHOLD_PROPOSAL.yaml",
    "CONTACT_INPUT_AUDIT.json",
}


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_rename_directory_noreplace(source: Path, destination: Path) -> None:
    """Publish a same-filesystem directory with Linux RENAME_NOREPLACE."""

    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(library, "renameat2", None)
    if renameat2 is None:
        raise HartleyH0H2Error("atomic no-replace directory rename is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    at_fdcwd = -100
    rename_noreplace = 1
    result = renameat2(
        at_fdcwd,
        os.fsencode(source),
        at_fdcwd,
        os.fsencode(destination),
        rename_noreplace,
    )
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise FileExistsError(f"final Hartley audit root already exists: {destination}")
    raise OSError(error, os.strerror(error), str(destination))


def _validate_audit_transaction(root: Path) -> None:
    actual = {path.name for path in root.iterdir()}
    if actual != _AUDIT_OUTPUT_NAMES or any(not path.is_file() for path in root.iterdir()):
        raise HartleyH0H2Error("temporary audit output set is incomplete or contains extras")
    for name in (
        "BY2_PROJECTION_AUDIT_SUMMARY.json",
        "BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json",
        "BY2_TRAILING_RECORD_LEDGER.json",
        "FK_PROXY_AUDIT.json",
        "FK_PROXY_COVARIANCE_SUMMARY.json",
        "CONTACT_INPUT_AUDIT.json",
    ):
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise HartleyH0H2Error(f"temporary JSON audit is not an object: {name}")
    threshold = yaml.safe_load(
        (root / "CONTACT_THRESHOLD_PROPOSAL.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(threshold, dict):
        raise HartleyH0H2Error("temporary contact-threshold audit is not an object")
    for name in (
        "FK_PROXY_AUDIT.csv",
        "FK_PROXY_COVARIANCE_ESTIMATION.csv",
        "CONTACT_FORCE_DISTRIBUTIONS.csv",
        "CONTACT_SPEED_DISTRIBUTIONS.csv",
        "CONTACT_TRANSITION_AUDIT.csv",
    ):
        with (root / name).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or next(reader, None) is None:
                raise HartleyH0H2Error(f"temporary CSV audit is empty: {name}")


def _remove_owned_transaction_temp(temp: Path, parent: Path, prefix: str) -> None:
    if not temp.exists():
        return
    resolved_parent = parent.resolve(strict=True)
    resolved_temp = temp.resolve(strict=True)
    if (
        resolved_temp.parent != resolved_parent
        or not resolved_temp.name.startswith(prefix)
        or resolved_temp.is_symlink()
    ):
        raise HartleyH0H2Error("refusing cleanup outside the exact owned audit temp directory")
    shutil.rmtree(resolved_temp)


def write_hartley_input_audit(
    output_root: str | Path,
    audit: Mapping[str, Any],
    *,
    source_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Transactionally publish one complete audit directory without replacement."""

    blocker = hartley_audit_prepublication_blocker(audit)
    if blocker is not None:
        raise HartleyH0H2Error(
            f"{blocker['terminal_status']}: {blocker['error']}"
        )
    root = Path(output_root).resolve(strict=False)
    if os.path.lexists(root):
        raise FileExistsError(f"final Hartley audit root already exists: {root}")
    parent = root.parent
    parent.mkdir(parents=True, exist_ok=True)
    prefix = f".{root.name}.hartley-audit-tmp-"
    temp = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    summary = dict(audit["summary"])
    if source_identity is not None:
        summary["source_identity"] = dict(source_identity)
    try:
        _write_new_json(temp / "BY2_PROJECTION_AUDIT_SUMMARY.json", summary)
        _write_new_json(
            temp / "BY2_COMPLETE_RECORD_PREFIX_MANIFEST.json",
            audit["record_prefix_manifest"],
        )
        _write_new_json(
            temp / "BY2_TRAILING_RECORD_LEDGER.json",
            audit["trailing_record_ledger"],
        )
        _write_new_csv(temp / "FK_PROXY_AUDIT.csv", audit["fk_rows"])
        _write_new_json(temp / "FK_PROXY_AUDIT.json", audit["fk_report"])
        _write_new_csv(
            temp / "FK_PROXY_COVARIANCE_ESTIMATION.csv", audit["fk_covariance_rows"]
        )
        _write_new_json(
            temp / "FK_PROXY_COVARIANCE_SUMMARY.json", audit["fk_covariance_report"]
        )
        _write_new_csv(
            temp / "CONTACT_FORCE_DISTRIBUTIONS.csv", audit["force_distribution_rows"]
        )
        _write_new_csv(
            temp / "CONTACT_SPEED_DISTRIBUTIONS.csv", audit["speed_distribution_rows"]
        )
        transition_rows = list(audit["transition_rows"])
        if not transition_rows:
            raise HartleyH0H2Error("stable contact audit unexpectedly has no transition rows")
        _write_new_csv(temp / "CONTACT_TRANSITION_AUDIT.csv", transition_rows)
        _write_new_text(
            temp / "CONTACT_THRESHOLD_PROPOSAL.yaml",
            yaml.safe_dump(
                audit["contact_threshold_proposal"],
                sort_keys=False,
                allow_unicode=True,
            ),
        )
        _write_new_json(temp / "CONTACT_INPUT_AUDIT.json", audit["contact_report"])
        _validate_audit_transaction(temp)
        _fsync_directory(temp)
        if os.path.lexists(root):
            raise FileExistsError(f"final Hartley audit root appeared during transaction: {root}")
        _atomic_rename_directory_noreplace(temp, root)
        _fsync_directory(parent)
    except Exception:
        _remove_owned_transaction_temp(temp, parent, prefix)
        raise
    return summary


__all__ = [
    "BY2_COMPLETE_RECORD_POLICY_ID",
    "BY2_RELATIVE_PATH",
    "BY2_HASH_LOCK_COLUMNS",
    "CANONICAL_FOOT_ORDER",
    "CANONICAL_TO_NATIVE",
    "CONTACT_STABILITY_MIN_STATE_FRACTION",
    "ContactDetectorConfig",
    "ContactInputNotIdentifiable",
    "CompleteRecordPolicy",
    "CompleteRecordScanResult",
    "DEFAULT_MINIMUM_DWELL_SAMPLES",
    "EXPECTED_BY2_MESSAGE_COUNT",
    "EXPECTED_BY2_USABLE_RECORD_COUNT",
    "FROZEN_CONTACT_DWELL_SAMPLES",
    "FROZEN_CONTACT_DWELL_SECONDS",
    "FROZEN_CONTACT_OFF_THRESHOLDS",
    "FROZEN_CONTACT_ON_THRESHOLDS",
    "HARTLEY_INPUT_AUDIT_RELATIVE",
    "HartleyAuditPaths",
    "HartleyH0H2Error",
    "HartleyInputRecord",
    "IMU_INSTALL_RPY_DEG",
    "NATIVE_FOOT_ORDER",
    "NATIVE_TO_CANONICAL",
    "PRODUCTION_COMPLETE_RECORD_POLICY_V1",
    "PhysicalRecordEvidence",
    "RequiredFieldError",
    "build_hartley_input_audit",
    "canonical_to_native_foot_order",
    "contact_diagnostic_audit",
    "complete_record_prefix_manifest",
    "compute_fk_proxy_covariance",
    "derive_force_contact_proposal",
    "euler_rpy_deg_to_matrix",
    "fk_proxy_audit",
    "force_hysteresis_contacts",
    "frozen_force_contact_states",
    "hartley_audit_prepublication_blocker",
    "hartley_world_up_gauge_to_reporting_down_gauge",
    "installation_rotation_candidates",
    "iter_hartley_input_projection",
    "native_to_canonical_foot_order",
    "resolve_hartley_audit_paths",
    "scan_hartley_complete_record_prefix",
    "sha256_file",
    "stationary_gravity_cancellation",
    "timing_audit",
    "trailing_record_ledger",
    "TRUSTED_BY2_HASH_LOCK_SHA256",
    "validate_rotation_matrix",
    "verify_by2_hash_lock",
    "write_hartley_input_audit",
]
