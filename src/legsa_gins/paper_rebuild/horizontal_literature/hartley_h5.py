"""Preregistered H5 BY2 input/cache and native-output contracts.

This module deliberately has no reference-data reader.  Its streaming parser
decodes only timestamp, body IMU, foot force, and body-frame foot position.
Every other field is skipped lexically, so even malformed forbidden values
cannot become an online dependency.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Iterator, Mapping, Sequence

import numpy as np
import yaml

from .hartley_h0_h2 import (
    BY2_RELATIVE_PATH,
    CANONICAL_FOOT_ORDER,
    FROZEN_CONTACT_DWELL_SAMPLES,
    FROZEN_CONTACT_DWELL_SECONDS,
    FROZEN_CONTACT_OFF_THRESHOLDS,
    FROZEN_CONTACT_ON_THRESHOLDS,
    IMU_INSTALL_RPY_DEG,
    NATIVE_TO_CANONICAL,
    PRODUCTION_BY2_FIRST_COMPLETE_TIMESTAMP_NS,
    PRODUCTION_BY2_LAST_COMPLETE_TIMESTAMP_NS,
    PRODUCTION_BY2_PREFIX_END_EXCLUSIVE,
    PRODUCTION_BY2_PREFIX_SHA256,
    PRODUCTION_BY2_RAW_SHA256,
    PRODUCTION_BY2_RAW_SIZE_BYTES,
)

H5_BACKEND_ID = "HARTLEY_IJRR2020_REPORTED_BACKEND"
H5_PRIMARY_RUN_ID = "H5_PRIMARY_GO2_ALLAN_EQ61_FK10MM"
H5_RUN_IDS = (
    H5_PRIMARY_RUN_ID,
    "H5_FK05MM_SENSITIVITY",
    "H5_FK20MM_SENSITIVITY",
    "H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY",
)
PRODUCTION_H5_RECORD_COUNT = 63_277
H5_RECORD_COUNT = PRODUCTION_H5_RECORD_COUNT
H5_PROPAGATION_COUNT = 63_276
H5_FROZEN_TRANSITION_EVENT_COUNT = 4_706
H5_PREFIX_INTERVAL = (0, PRODUCTION_BY2_PREFIX_END_EXCLUSIVE)
H5_SENSOR_TO_BODY_ROLL_DEG = -1.0

CACHE_MAGIC = b"LEGS_H5_CACHE\0\0\0"
CACHE_VERSION = 1
CACHE_HEADER_SIZE = 256
CACHE_RECORD_SIZE = 192
CACHE_HEADER_STRUCT = struct.Struct("<16sIIIIQqq32s32s32s104x")
CACHE_RECORD_STRUCT = struct.Struct("<q22dBBBB4x")
assert CACHE_HEADER_STRUCT.size == CACHE_HEADER_SIZE
assert CACHE_RECORD_STRUCT.size == CACHE_RECORD_SIZE

OUTPUT_SCHEMAS: Mapping[str, tuple[str, ...]] = {
    "NAV.csv": ("timestamp_ns", "row_index", "state_role", "active_contact_count", "state_dimension", "r00", "r01", "r02", "r10", "r11", "r12", "r20", "r21", "r22", "vx", "vy", "vz", "px", "py", "pz", "bgx", "bgy", "bgz", "bax", "bay", "baz"),
    "COVARIANCE_DIAGONALS.csv": (
        "timestamp_ns", "row_index", "topology", "dimension",
        "theta_x", "theta_y", "theta_z", "velocity_x", "velocity_y", "velocity_z",
        "position_x", "position_y", "position_z",
        "contact_FL_x", "contact_FL_y", "contact_FL_z",
        "contact_FR_x", "contact_FR_y", "contact_FR_z",
        "contact_RL_x", "contact_RL_y", "contact_RL_z",
        "contact_RR_x", "contact_RR_y", "contact_RR_z",
        "gyro_bias_x", "gyro_bias_y", "gyro_bias_z",
        "accel_bias_x", "accel_bias_y", "accel_bias_z",
        "gauge_yaw_variance", "gauge_translation_x_variance",
        "gauge_translation_y_variance", "gauge_translation_z_variance",
    ),
    "COVARIANCE_CHECKPOINT_INDEX.csv": ("checkpoint_index", "row_index", "timestamp_ns", "reason", "topology", "dimension", "npz_key"),
    "CONTACT_STATE.csv": ("timestamp_ns", "row_index", "leg_id", "leg", "active", "contact_x", "contact_y", "contact_z"),
    "CONTACT_EVENT_LEDGER.csv": ("timestamp_ns", "row_index", "leg_id", "leg", "event", "force", "contact_mask", "add_mask", "remove_mask"),
    "KINEMATIC_INNOVATIONS.csv": ("timestamp_ns", "row_index", "leg_id", "leg", "innovation_x", "innovation_y", "innovation_z"),
    "NIS_DIAGNOSTICS.csv": ("timestamp_ns", "row_index", "contact_count", "nis", "factorization_ok"),
    "RUNTIME.csv": ("run_id", "backend_id", "state_rows", "propagation_calls", "eq61_calls", "eq52_calls", "threads_verified", "elapsed_seconds"),
    "NATIVE_COMPARISON.csv": ("run_id", "comparison_scope", "reference_opened", "trace_used", "state_rows", "final_position_norm_m", "final_velocity_norm_m_per_s"),
    "EXECUTION_LEDGER.csv": ("input_row", "output_row", "timestamp_ns", "dt_seconds", "active_contacts_before", "active_contacts_after", "state_dimension", "propagation_status", "update_status", "add_mask", "remove_mask"),
}
JSON_OUTPUTS = ("NATIVE_SUMMARY.json", "NATIVE_FREEZE.json")


class HartleyH5Error(ValueError):
    pass


@dataclass(frozen=True)
class H5Record:
    timestamp_ns: int
    gyro_body: tuple[float, float, float]
    accel_body: tuple[float, float, float]
    foot_force_canonical: tuple[float, float, float, float]
    foot_position_body_canonical: tuple[tuple[float, float, float], ...]
    contact_mask: int
    add_mask: int
    remove_mask: int


@dataclass(frozen=True)
class SemanticReadCounters:
    timestamp_values: int = 0
    gyro_values: int = 0
    accel_values: int = 0
    foot_force_values: int = 0
    foot_position_values: int = 0
    forbidden_or_audit_values_decoded: int = 0
    lexically_skipped_lines: int = 0


@dataclass(frozen=True)
class H5SourceIdentity:
    source: Path
    raw_size: int
    raw_sha256: str
    prefix_end_exclusive: int
    prefix_sha256: str


def sha256_file(path: Path, *, limit: int | None = None) -> str:
    digest = hashlib.sha256()
    remaining = limit
    with path.open("rb") as handle:
        while remaining is None or remaining > 0:
            size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
            block = handle.read(size)
            if not block:
                break
            digest.update(block)
            if remaining is not None:
                remaining -= len(block)
    if remaining not in (None, 0):
        raise HartleyH5Error("source ended before the locked prefix boundary")
    return digest.hexdigest()


def resolve_h5_source(paths_config: str | Path) -> Path:
    config_path = Path(paths_config)
    if config_path.name != "DATA_PATHS.CLEAN3R4.local.yaml":
        raise HartleyH5Error("H5 source may resolve only through ignored DATA_PATHS.CLEAN3R4.local.yaml")
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("paths"), dict):
        raise HartleyH5Error("local paths configuration is malformed")
    paths = payload["paths"]
    explicit = paths.get("by2_go2_body")
    if explicit is not None:
        source = Path(str(explicit))
    elif paths.get("raw_root") is not None:
        source = Path(str(paths["raw_root"])) / BY2_RELATIVE_PATH
    else:
        raise HartleyH5Error("local paths configuration lacks by2_go2_body/raw_root")
    source = source.resolve(strict=True)
    if not source.is_file():
        raise HartleyH5Error("resolved H5 BY2 source is not a regular file")
    return source


def verify_source_identity(
    source: Path,
    *,
    expected_raw_size: int = PRODUCTION_BY2_RAW_SIZE_BYTES,
    expected_raw_sha256: str = PRODUCTION_BY2_RAW_SHA256,
    prefix_end_exclusive: int = PRODUCTION_BY2_PREFIX_END_EXCLUSIVE,
    expected_prefix_sha256: str = PRODUCTION_BY2_PREFIX_SHA256,
) -> H5SourceIdentity:
    before = source.stat()
    raw_hash = sha256_file(source)
    prefix_hash = sha256_file(source, limit=prefix_end_exclusive)
    after = source.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise HartleyH5Error("raw source changed during identity verification")
    if (before.st_size, raw_hash) != (expected_raw_size, expected_raw_sha256):
        raise HartleyH5Error("raw size/SHA identity mismatch")
    if prefix_hash != expected_prefix_sha256:
        raise HartleyH5Error("complete-prefix SHA identity mismatch")
    return H5SourceIdentity(source, before.st_size, raw_hash, prefix_end_exclusive, prefix_hash)


def _finite_number(text: str, label: str) -> float:
    try:
        value = float(text.strip().split("#", 1)[0])
    except ValueError as exc:
        raise HartleyH5Error(f"malformed allowed numeric field {label}") from exc
    if not math.isfinite(value):
        raise HartleyH5Error(f"nonfinite allowed numeric field {label}")
    return value


def _integer(text: str, label: str) -> int:
    value = text.strip().split("#", 1)[0]
    if not value or any(character not in "+-0123456789" for character in value):
        raise HartleyH5Error(f"malformed allowed integer field {label}")
    return int(value)


def _inline_array(text: str, label: str) -> list[float]:
    value = text.strip().split("#", 1)[0].strip()
    if not value.startswith("[") or not value.endswith("]"):
        raise HartleyH5Error(f"allowed field {label} is not an inline array")
    body = value[1:-1].strip()
    return [] if not body else [_finite_number(item, label) for item in body.split(",")]


def _rotation_x_minus_one_degree(values: Sequence[float]) -> tuple[float, float, float]:
    angle = math.radians(H5_SENSOR_TO_BODY_ROLL_DEG)
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = values
    return (x, c * y - s * z, s * y + c * z)


def _parse_allowed_record(lines: Iterable[str], record_index: int) -> tuple[int, list[float], list[float], list[float], list[float], SemanticReadCounters]:
    sec: int | None = None
    nanosec: int | None = None
    gyro: list[float] = []
    accel: list[float] = []
    force: list[float] = []
    feet: list[float] = []
    top = ""
    active = ""
    counts = {"timestamp": 0, "gyro": 0, "accel": 0, "force": 0, "feet": 0, "skip": 0}
    targets = {"gyroscope": gyro, "accelerometer": accel, "foot_force": force, "foot_position_body": feet}
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped in ("---", "..."):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0 and ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            top, active = key, ""
            if key in ("stamp", "imu_state"):
                continue
            if key in ("foot_force", "foot_position_body"):
                if value.strip():
                    targets[key].extend(_inline_array(value, key))
                else:
                    active = key
                continue
            # Critical: do not inspect, tokenize, or convert unknown values.
            top = ""
            counts["skip"] += 1
            continue
        if top == "stamp" and ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            if key.strip() == "sec":
                sec = _integer(value, "stamp.sec")
                counts["timestamp"] += 1
            elif key.strip() == "nanosec":
                nanosec = _integer(value, "stamp.nanosec")
                counts["timestamp"] += 1
            else:
                counts["skip"] += 1
            continue
        if top == "imu_state" and ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            active = ""
            if key in ("gyroscope", "accelerometer"):
                if value.strip():
                    targets[key].extend(_inline_array(value, key))
                else:
                    active = key
            else:
                counts["skip"] += 1
            continue
        if active and stripped.startswith("-"):
            targets[active].append(_finite_number(stripped[1:], active))
        else:
            counts["skip"] += 1
    shapes = (len(gyro), len(accel), len(force), len(feet))
    if sec is None or nanosec is None or shapes != (3, 3, 4, 12):
        raise HartleyH5Error(f"H5 record {record_index} allowed-field shape failure: {shapes}")
    if not 0 <= nanosec < 1_000_000_000:
        raise HartleyH5Error(f"H5 record {record_index} nanosec outside [0,1e9)")
    counter = SemanticReadCounters(
        timestamp_values=counts["timestamp"], gyro_values=len(gyro),
        accel_values=len(accel), foot_force_values=len(force),
        foot_position_values=len(feet), forbidden_or_audit_values_decoded=0,
        lexically_skipped_lines=counts["skip"],
    )
    return sec * 1_000_000_000 + nanosec, gyro, accel, force, feet, counter


def _sum_counters(lhs: SemanticReadCounters, rhs: SemanticReadCounters) -> SemanticReadCounters:
    return SemanticReadCounters(**{key: getattr(lhs, key) + getattr(rhs, key) for key in asdict(lhs)})


class ContactHysteresis:
    def __init__(self) -> None:
        self.active = [False] * 4
        self.initialized = False
        self.candidate: list[bool | None] = [None] * 4
        self.candidate_start_seconds: list[float | None] = [None] * 4

    def update(self, timestamp_ns: int, force: Sequence[float]) -> tuple[int, int, int]:
        before = list(self.active)
        timestamp_seconds = timestamp_ns / 1.0e9
        if not self.initialized:
            self.active = [
                value >= 0.5 * (FROZEN_CONTACT_ON_THRESHOLDS[index] +
                                FROZEN_CONTACT_OFF_THRESHOLDS[index])
                for index, value in enumerate(force)
            ]
            self.initialized = True
            mask = sum((1 << index) for index, value in enumerate(self.active) if value)
            return mask, mask, 0
        for index, value in enumerate(force):
            desired: bool | None = None
            if self.active[index] and value <= FROZEN_CONTACT_OFF_THRESHOLDS[index]:
                desired = False
            elif not self.active[index] and value >= FROZEN_CONTACT_ON_THRESHOLDS[index]:
                desired = True
            if desired is None:
                self.candidate[index] = None
                self.candidate_start_seconds[index] = None
                continue
            if self.candidate[index] != desired:
                self.candidate[index] = desired
                self.candidate_start_seconds[index] = timestamp_seconds
            assert self.candidate_start_seconds[index] is not None
            elapsed = timestamp_seconds - self.candidate_start_seconds[index]
            if elapsed + 1.0e-12 >= FROZEN_CONTACT_DWELL_SECONDS:
                self.active[index] = desired
                self.candidate[index] = None
                self.candidate_start_seconds[index] = None
        mask = sum((1 << index) for index, value in enumerate(self.active) if value)
        add = sum((1 << index) for index in range(4) if self.active[index] and not before[index])
        remove = sum((1 << index) for index in range(4) if before[index] and not self.active[index])
        return mask, add, remove


def stream_h5_prefix(
    source: Path,
    *,
    prefix_end_exclusive: int = PRODUCTION_BY2_PREFIX_END_EXCLUSIVE,
    expected_records: int = H5_RECORD_COUNT,
) -> tuple[Iterator[H5Record], dict[str, Any]]:
    counters = SemanticReadCounters()
    summary: dict[str, Any] = {"semantic_read_counters": None}

    def iterator() -> Iterator[H5Record]:
        nonlocal counters
        detector = ContactHysteresis()
        previous_ns: int | None = None
        record_lines: list[str] = []
        byte_offset = 0
        emitted = 0
        with source.open("rb") as handle:
            while byte_offset < prefix_end_exclusive:
                binary = handle.readline()
                if not binary:
                    raise HartleyH5Error("source ended inside locked prefix")
                byte_offset += len(binary)
                if byte_offset > prefix_end_exclusive:
                    raise HartleyH5Error("prefix boundary splits a physical line")
                try:
                    line = binary.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise HartleyH5Error("raw prefix is not strict UTF-8") from exc
                if line.strip() == "stamp:" and not line[:1].isspace():
                    if record_lines:
                        raise HartleyH5Error("record start encountered before delimiter")
                    record_lines = [line]
                    continue
                if not record_lines:
                    # Header/prologue is skipped lexically.
                    continue
                record_lines.append(line)
                if line.strip() != "---":
                    continue
                emitted += 1
                timestamp_ns, gyro, accel, force_native, feet_native, row_counts = _parse_allowed_record(record_lines, emitted)
                counters = _sum_counters(counters, row_counts)
                if previous_ns is not None and timestamp_ns <= previous_ns:
                    raise HartleyH5Error("timestamps are not strictly increasing integer nanoseconds")
                previous_ns = timestamp_ns
                force = tuple(force_native[index] for index in NATIVE_TO_CANONICAL)
                grouped = tuple(tuple(feet_native[index:index + 3]) for index in range(0, 12, 3))
                feet = tuple(grouped[index] for index in NATIVE_TO_CANONICAL)
                mask, add, remove = detector.update(timestamp_ns, force_native)
                # Detector masks originate in native order; remap to canonical bits.
                def canonical_mask(native_mask: int) -> int:
                    return sum((1 << canonical) for canonical, native in enumerate(NATIVE_TO_CANONICAL) if native_mask & (1 << native))
                yield H5Record(timestamp_ns, _rotation_x_minus_one_degree(gyro),
                               _rotation_x_minus_one_degree(accel), force, feet,
                               canonical_mask(mask), canonical_mask(add), canonical_mask(remove))
                record_lines = []
        if record_lines:
            raise HartleyH5Error("locked prefix ended with an undelimited record")
        if byte_offset != prefix_end_exclusive or emitted != expected_records:
            raise HartleyH5Error("locked prefix byte/record count mismatch")
        summary["semantic_read_counters"] = asdict(counters)
        summary["record_count"] = emitted
        summary["first_timestamp_ns"] = None if emitted == 0 else summary.get("first_timestamp_ns")
    return iterator(), summary


def encode_cache_record(record: H5Record) -> bytes:
    values: list[float] = [*record.gyro_body, *record.accel_body, *record.foot_force_canonical]
    for foot in record.foot_position_body_canonical:
        values.extend(foot)
    if len(values) != 22:
        raise AssertionError("H5 cache record requires exactly 22 float64 values")
    return CACHE_RECORD_STRUCT.pack(record.timestamp_ns, *values, record.contact_mask,
                                    record.add_mask, record.remove_mask, 0)


def exclusive_write_bytes(path: Path, chunks: Iterable[bytes]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)
    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            for chunk in chunks:
                handle.write(chunk)
                digest.update(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        # Preserve failed attempts; never unlink a possibly useful artifact.
        raise
    return digest.hexdigest()


def build_immutable_cache(identity: H5SourceIdentity, cache_path: Path, event_ledger_path: Path,
                          *, expected_records: int = H5_RECORD_COUNT) -> dict[str, Any]:
    records, parse_summary = stream_h5_prefix(identity.source, prefix_end_exclusive=identity.prefix_end_exclusive,
                                               expected_records=expected_records)
    materialized = list(records)
    if len(materialized) != expected_records:
        raise HartleyH5Error("cache row count mismatch")
    events = [json.dumps({"row_index": index, "timestamp_ns": row.timestamp_ns,
                          "contact_mask": row.contact_mask, "add_mask": row.add_mask,
                          "remove_mask": row.remove_mask}, sort_keys=True, separators=(",", ":")) + "\n"
              for index, row in enumerate(materialized) if row.add_mask or row.remove_mask]
    event_bytes = [value.encode("utf-8") for value in events]
    initial_add_event_count = materialized[0].add_mask.bit_count()
    transition_event_count = sum(
        row.add_mask.bit_count() + row.remove_mask.bit_count()
        for row in materialized[1:]
    )
    if expected_records == PRODUCTION_H5_RECORD_COUNT and transition_event_count != H5_FROZEN_TRANSITION_EVENT_COUNT:
        raise HartleyH5Error("H5 contact transitions differ from frozen 4,706-event audit")
    event_hash = exclusive_write_bytes(event_ledger_path, event_bytes)
    header = CACHE_HEADER_STRUCT.pack(
        CACHE_MAGIC, CACHE_VERSION, CACHE_HEADER_SIZE, CACHE_RECORD_SIZE,
        len(materialized), identity.prefix_end_exclusive,
        materialized[0].timestamp_ns, materialized[-1].timestamp_ns,
        bytes.fromhex(identity.raw_sha256), bytes.fromhex(identity.prefix_sha256),
        bytes.fromhex(event_hash),
    )
    cache_hash = exclusive_write_bytes(cache_path, [header, *(encode_cache_record(row) for row in materialized)])
    return {
        "schema_version": "hartley.h5.cache_manifest.v1",
        "cache_sha256": cache_hash,
        "event_ledger_sha256": event_hash,
        "cache_header_size": CACHE_HEADER_SIZE,
        "cache_record_size": CACHE_RECORD_SIZE,
        "record_count": len(materialized),
        "first_timestamp_ns": materialized[0].timestamp_ns,
        "last_timestamp_ns": materialized[-1].timestamp_ns,
        "cache_size_bytes": CACHE_HEADER_SIZE + len(materialized) * CACHE_RECORD_SIZE,
        "cache_schema": {
            "byte_order": "little_endian", "header_bytes": CACHE_HEADER_SIZE,
            "record_bytes": CACHE_RECORD_SIZE, "float64_value_count": 22,
        },
        "frozen_transition_event_count_excluding_initial_add": transition_event_count,
        "initial_add_event_count": initial_add_event_count,
        "semantic_read_counters": parse_summary["semantic_read_counters"],
        "raw_sha256": identity.raw_sha256,
        "prefix_sha256": identity.prefix_sha256,
        "prefix_interval": list(H5_PREFIX_INTERVAL),
        "canonical_foot_order": list(CANONICAL_FOOT_ORDER),
        "sensor_to_body_rpy_deg": list(IMU_INSTALL_RPY_DEG),
        "no_imputation": True,
        "no_interpolation": True,
    }


def verify_single_thread_environment(environment: Mapping[str, str] = os.environ) -> dict[str, str]:
    keys = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    actual = {key: environment.get(key, "") for key in keys}
    if any(value != "1" for value in actual.values()):
        raise HartleyH5Error("OMP/MKL/OPENBLAS/NUMEXPR thread counts must all equal 1")
    return actual


def checkpoint_rows(timestamps_ns: Sequence[int], lifecycle_rows: Iterable[int], settled_rows: Iterable[int]) -> tuple[int, ...]:
    if not timestamps_ns:
        raise HartleyH5Error("checkpoint schedule requires timestamps")
    selected = {0, len(timestamps_ns) - 1, *lifecycle_rows, *settled_rows}
    origin = timestamps_ns[0]
    last_elapsed_second = (timestamps_ns[-1] - origin) // 1_000_000_000
    for second in range(int(last_elapsed_second) + 1):
        target = origin + second * 1_000_000_000
        # min tuple implements earlier-row tie-break.
        selected.add(min(range(len(timestamps_ns)), key=lambda index: (abs(timestamps_ns[index] - target), index)))
    return tuple(sorted(selected))


def checkpoint_reason_map(
    timestamps_ns: Sequence[int], lifecycle_rows: Iterable[int]
) -> dict[int, tuple[str, ...]]:
    if not timestamps_ns:
        raise HartleyH5Error("checkpoint schedule requires timestamps")
    reasons: dict[int, set[str]] = {0: {"first"}, len(timestamps_ns) - 1: {"last"}}
    for row in lifecycle_rows:
        reasons.setdefault(int(row), set()).add("contact_event_after_settled_lifecycle")
    origin = timestamps_ns[0]
    last_second = (timestamps_ns[-1] - origin) // 1_000_000_000
    for second in range(int(last_second) + 1):
        target = origin + second * 1_000_000_000
        row = min(range(len(timestamps_ns)),
                  key=lambda index: (abs(timestamps_ns[index] - target), index))
        reasons.setdefault(row, set()).add("integer_second")
    return {row: tuple(sorted(values)) for row, values in sorted(reasons.items())}


def gauge_projection(dimension: int, active_contact_ids: Sequence[int]) -> tuple[np.ndarray, tuple[str, ...]]:
    expected = 15 + 3 * len(active_contact_ids)
    if dimension != expected:
        raise HartleyH5Error("gauge projection topology/dimension mismatch")
    columns = np.zeros((dimension, 4), dtype=float)
    columns[2, 0] = -1.0  # normalized gravity direction [0,0,-1]
    translation_blocks = [6, *(9 + 3 * index for index in range(len(active_contact_ids)))]
    normalization = math.sqrt(len(active_contact_ids) + 1.0)
    for axis in range(3):
        for block in translation_blocks:
            columns[block + axis, 1 + axis] = 1.0 / normalization
    labels = ("yaw_about_unit_gravity", "common_translation_x", "common_translation_y", "common_translation_z")
    return columns, labels


def validate_output_schema(name: str, columns: Sequence[str]) -> None:
    expected = OUTPUT_SCHEMAS.get(name)
    if expected is None or tuple(columns) != expected:
        raise HartleyH5Error(f"native output schema mismatch for {name}")


def freeze_native_outputs(run_directory: Path) -> dict[str, Any]:
    required = (*OUTPUT_SCHEMAS.keys(), "NATIVE_CONFIG.cfg", "NATIVE_SUMMARY.json",
                "COVARIANCE_CHECKPOINTS.npz")
    paths = [run_directory / name for name in required]
    if any(not path.is_file() for path in paths):
        raise HartleyH5Error("native freeze requires the exact complete output manifest")
    manifest = {path.name: {"size": path.stat().st_size, "sha256": sha256_file(path)} for path in paths}
    payload = json.dumps({"schema_version": "hartley.h5.native_freeze.v1", "files": manifest}, sort_keys=True, indent=2).encode() + b"\n"
    freeze_path = run_directory / "NATIVE_FREEZE.json"
    exclusive_write_bytes(freeze_path, [payload])
    loaded = json.loads(freeze_path.read_text(encoding="utf-8"))
    if loaded.get("files") != manifest:
        raise HartleyH5Error("native freeze self-verification failed")
    return manifest


def publish_exact_manifest(source_directory: Path, destination_directory: Path, manifest: Mapping[str, Mapping[str, Any]]) -> None:
    for name, identity in manifest.items():
        if Path(name).name != name:
            raise HartleyH5Error("publication manifest contains a non-basename")
        source = source_directory / name
        if source.stat().st_size != int(identity["size"]) or sha256_file(source) != identity["sha256"]:
            raise HartleyH5Error("publication source differs from frozen manifest")
    destination_directory.mkdir(parents=True, exist_ok=False)
    for name in manifest:
        source = source_directory / name
        def chunks() -> Iterator[bytes]:
            with source.open("rb") as handle:
                while True:
                    block = handle.read(1024 * 1024)
                    if not block:
                        return
                    yield block
        exclusive_write_bytes(destination_directory / name, chunks())


__all__ = [name for name in globals() if name.startswith("H5_") or name in {
    "CACHE_HEADER_SIZE", "CACHE_RECORD_SIZE", "CACHE_HEADER_STRUCT", "CACHE_RECORD_STRUCT",
    "HartleyH5Error", "H5Record", "SemanticReadCounters", "ContactHysteresis",
    "resolve_h5_source", "verify_source_identity", "stream_h5_prefix", "encode_cache_record",
    "build_immutable_cache", "verify_single_thread_environment", "checkpoint_rows",
    "checkpoint_reason_map", "gauge_projection", "validate_output_schema", "freeze_native_outputs", "publish_exact_manifest",
}]
