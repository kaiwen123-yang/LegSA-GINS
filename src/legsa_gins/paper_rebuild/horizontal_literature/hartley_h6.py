"""Hartley H6 real-data yaw-gauge and numerical-observability workflow.

The module consumes only the frozen H5 proprioceptive cache and H5 native
anchor.  It has no path resolver or reader for reference, trace, GNSS, Go2
onboard pose/yaw, LegSA output, EXT output, or any later H7 artifact.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np
import yaml
from scipy.linalg import null_space
from scipy.stats import chi2

from . import hartley_h5 as h5


TASK_START_HEAD = "4b25fa6337f4760557f501f102a38a1ac65c766e"
METHOD_ID = "LSE01_HARTLEY_CONTACT_AIDED_INEKF"
BACKEND_ID = "HARTLEY_IJRR2020_REPORTED_BACKEND"
PROCESS_PROFILE = "GO2_IMU_ALLAN_90MIN_RECOVERED_V1_PLUS_PAPER_NATIVE_CONTACT_EQ61"
SIGMA_FK_M = 0.010
STATE_ROWS = 63_277
PROPAGATION_CALLS = 63_276
RAW_SHA256 = "95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278"
PREFIX_SHA256 = "03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097"
CACHE_SHA256 = "c169e26d66f35fe200bb17a695353cd2d751482df1cd97996a7a8afff8662065"
EVENT_LEDGER_SHA256 = "8e80cde9b90ade49753d8fd97e554af3c032c664d1d336f663838cbb68204358"
THREAD_KEYS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
GRAVITY = np.asarray([0.0, 0.0, -9.81], dtype=float)
LEGS = ("FL", "FR", "RL", "RR")

YAW_MEMBERS: tuple[tuple[str, float, str], ...] = (
    ("H6_YAW_M150", -150.0, "01_YAW_M150"),
    ("H6_YAW_M100", -100.0, "02_YAW_M100"),
    ("H6_YAW_M050", -50.0, "03_YAW_M050"),
    ("H6_YAW_P050", 50.0, "05_YAW_P050"),
    ("H6_YAW_P100", 100.0, "06_YAW_P100"),
    ("H6_YAW_P150", 150.0, "07_YAW_P150"),
)
YAW_BY_RUN_ID = {run_id: yaw for run_id, yaw, _ in YAW_MEMBERS}
DIRECTORY_BY_RUN_ID = {run_id: directory for run_id, _, directory in YAW_MEMBERS}
PARITY_RUN_ID = "H6_YAW_000_PARITY"

H6_COVARIANCE_COLUMNS = (
    "timestamp_ns", "row_index", "topology", "dimension",
    "theta_x", "theta_y", "theta_z",
    "velocity_x", "velocity_y", "velocity_z",
    "position_x", "position_y", "position_z",
    "gyro_bias_x", "gyro_bias_y", "gyro_bias_z",
    "accel_bias_x", "accel_bias_y", "accel_bias_z",
    "gauge_yaw_variance", "gauge_translation_x_variance",
    "gauge_translation_y_variance", "gauge_translation_z_variance",
)
INNOVATION_NORM_COLUMNS = (
    "timestamp_ns", "row_index", "contact_set", "contact_count",
    "stacked_innovation_norm", "nis", "factorization_success",
)
COMPACT_RUN_FILES = (
    "NAV.csv", "GAUGE_COVARIANCE_DIAGONALS.csv",
    "COVARIANCE_CHECKPOINT_INDEX.csv", "COVARIANCE_CHECKPOINTS.npz",
    "GAUGE_INNOVATION_NORMS.csv", "NATIVE_CONFIG.yaml",
    "NATIVE_SUMMARY.json", "RUNTIME.csv",
)


class HartleyH6Error(RuntimeError):
    """A frozen H6 contract or gate failed."""


@dataclass(frozen=True)
class CacheArrays:
    timestamp_ns: np.ndarray
    gyro: np.ndarray
    accel: np.ndarray
    foot_force: np.ndarray
    foot_position: np.ndarray
    contact_mask: np.ndarray
    add_mask: np.ndarray
    remove_mask: np.ndarray


@dataclass(frozen=True)
class NavArrays:
    timestamp_ns: np.ndarray
    rotation: np.ndarray
    velocity: np.ndarray
    position: np.ndarray
    gyro_bias: np.ndarray
    accel_bias: np.ndarray
    active_contact_count: np.ndarray
    state_dimension: np.ndarray


@dataclass(frozen=True)
class Segment:
    segment_id: str
    start_row: int
    end_row: int
    start_timestamp_ns: int
    end_timestamp_ns: int
    duration_seconds: float
    sample_count: int
    contact_mask: int
    contact_set: str
    contact_count: int
    gyro_rms_rad_per_s: float
    accelerometer_norm_variability_m_per_s2: float
    input_excitation_score: float
    excitation_label: str
    eligible: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(payload: Any) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()


def exclusive_write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        raise
    return hashlib.sha256(data).hexdigest()


def exclusive_json(path: Path, payload: Any) -> str:
    return exclusive_write(path, _canonical_json(payload))


def csv_bytes(rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(columns), lineterminator="\n")
    writer.writeheader()
    for source in rows:
        row: dict[str, Any] = {}
        for column in columns:
            value = source.get(column, "")
            if isinstance(value, (float, np.floating)):
                value = format(float(value), ".17g")
            elif isinstance(value, (bool, np.bool_)):
                value = "true" if bool(value) else "false"
            row[column] = value
        writer.writerow(row)
    return stream.getvalue().encode()


def exclusive_csv(path: Path, rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> str:
    return exclusive_write(path, csv_bytes(rows, columns))


def copy_exclusive(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    digest = hashlib.sha256()
    try:
        with source.open("rb") as source_handle, os.fdopen(descriptor, "wb", closefd=True) as output:
            for block in iter(lambda: source_handle.read(1024 * 1024), b""):
                output.write(block)
                digest.update(block)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        raise
    if destination.stat().st_size != source.stat().st_size or digest.hexdigest() != sha256_file(source):
        raise HartleyH6Error("exclusive copy parity failed")
    return digest.hexdigest()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not reader.fieldnames or any(None in row for row in rows):
        raise HartleyH6Error(f"malformed CSV: {path}")
    return rows


def _safe_remove_tree(path: Path, exact_parent: Path) -> None:
    if path.parent != exact_parent or not path.is_dir() or path.is_symlink() or path.resolve() != path:
        raise HartleyH6Error(f"unsafe exact scratch payload deletion: {path}")
    shutil.rmtree(path)
    if path.exists() or path.is_symlink():
        raise HartleyH6Error(f"scratch payload deletion failed: {path}")


def rotation_z(yaw_degrees: float) -> np.ndarray:
    # H6 alpha is defined about normalized world gravity e_g=[0,0,-1].
    # Therefore conventional +Z Euler yaw changes by -alpha.
    angle = -math.radians(float(yaw_degrees))
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.asarray(((cosine, -sine, 0.0), (sine, cosine, 0.0), (0.0, 0.0, 1.0)))


def wrap_pi(value: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(value) + math.pi) % (2.0 * math.pi) - math.pi


def gauge_transform_state(
    rotation: np.ndarray, velocity: np.ndarray, position: np.ndarray,
    contacts: Mapping[int, np.ndarray], gyro_bias: np.ndarray,
    accel_bias: np.ndarray, covariance: np.ndarray, yaw_degrees: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[int, np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    q = rotation_z(yaw_degrees)
    transformed_contacts = {identity: q @ value for identity, value in contacts.items()}
    dimension = covariance.shape[0]
    if covariance.shape != (dimension, dimension) or dimension != 15 + 3 * len(contacts):
        raise HartleyH6Error("initial gauge covariance/contact dimension mismatch")
    transform = np.eye(dimension)
    for offset in range(0, dimension - 6, 3):
        transform[offset:offset + 3, offset:offset + 3] = q
    return (
        q @ rotation, q @ velocity, q @ position, transformed_contacts,
        np.asarray(gyro_bias).copy(), np.asarray(accel_bias).copy(),
        transform @ covariance @ transform.T,
    )


def read_cache(path: Path) -> CacheArrays:
    if sha256_file(path) != CACHE_SHA256:
        raise HartleyH6Error("H6 provider-cache SHA-256 mismatch")
    dtype = np.dtype([
        ("timestamp_ns", "<i8"), ("values", "<f8", (22,)),
        ("contact_mask", "u1"), ("add_mask", "u1"),
        ("remove_mask", "u1"), ("reserved", "u1"), ("padding", "V4"),
    ])
    if dtype.itemsize != h5.CACHE_RECORD_SIZE:
        raise AssertionError("H5 cache dtype ABI mismatch")
    with path.open("rb") as handle:
        header = handle.read(h5.CACHE_HEADER_SIZE)
        records = np.fromfile(handle, dtype=dtype, count=STATE_ROWS)
        trailing = handle.read(1)
    unpacked = h5.CACHE_HEADER_STRUCT.unpack(header)
    if (
        len(records) != STATE_ROWS or trailing or unpacked[0] != h5.CACHE_MAGIC
        or unpacked[8].hex() != RAW_SHA256 or unpacked[9].hex() != PREFIX_SHA256
        or unpacked[10].hex() != EVENT_LEDGER_SHA256
    ):
        raise HartleyH6Error("H6 provider-cache header/row identity mismatch")
    values = records["values"]
    return CacheArrays(
        records["timestamp_ns"].astype(np.int64), values[:, 0:3].copy(),
        values[:, 3:6].copy(), values[:, 6:10].copy(),
        values[:, 10:22].reshape((-1, 4, 3)).copy(),
        records["contact_mask"].copy(), records["add_mask"].copy(),
        records["remove_mask"].copy(),
    )


def read_nav(path: Path) -> NavArrays:
    rows = _rows(path)
    if len(rows) != STATE_ROWS:
        raise HartleyH6Error("NAV row count is not 63,277")
    timestamp = np.asarray([int(row["timestamp_ns"]) for row in rows], dtype=np.int64)
    rotation = np.asarray([
        [float(row[f"r{axis // 3}{axis % 3}"]) for axis in range(9)] for row in rows
    ]).reshape((-1, 3, 3))
    vector = lambda names: np.asarray([[float(row[name]) for name in names] for row in rows])
    return NavArrays(
        timestamp, rotation, vector(("vx", "vy", "vz")), vector(("px", "py", "pz")),
        vector(("bgx", "bgy", "bgz")), vector(("bax", "bay", "baz")),
        np.asarray([int(row["active_contact_count"]) for row in rows]),
        np.asarray([int(row["state_dimension"]) for row in rows]),
    )


def read_contact_state(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows = _rows(path)
    if len(rows) != 4 * STATE_ROWS:
        raise HartleyH6Error("contact-state row count mismatch")
    active = np.zeros((STATE_ROWS, 4), dtype=bool)
    values = np.full((STATE_ROWS, 4, 3), np.nan)
    for offset, row in enumerate(rows):
        epoch, leg = divmod(offset, 4)
        if int(row["row_index"]) != epoch or int(row["leg_id"]) != leg or row["leg"] != LEGS[leg]:
            raise HartleyH6Error("contact-state identity/order mismatch")
        active[epoch, leg] = row["active"] == "1"
        if active[epoch, leg]:
            values[epoch, leg] = [float(row[name]) for name in ("contact_x", "contact_y", "contact_z")]
    return active, values


def innovation_norms(path: Path, state_rows: int = STATE_ROWS) -> np.ndarray:
    result = np.zeros(state_rows, dtype=float)
    squares = np.zeros(state_rows, dtype=float)
    for row in _rows(path):
        index = int(row["row_index"])
        squares[index] += sum(float(row[name]) ** 2 for name in ("innovation_x", "innovation_y", "innovation_z"))
    np.sqrt(squares, out=result)
    return result


def contact_set(mask: int) -> str:
    return "+".join(LEGS[index] for index in range(4) if mask & (1 << index)) or "NONE"


def _source_manifest(repository: Path, script_path: Path) -> tuple[str, dict[str, Any]]:
    relative_paths = (
        script_path.relative_to(repository).as_posix(),
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/run_h5.cpp",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/src/backend.cpp",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/include/hartley_inekf/backend.hpp",
        "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_H6_EXECUTION_CONTRACT.yaml",
    )
    files = {
        relative: {"size": (repository / relative).stat().st_size, "sha256": sha256_file(repository / relative)}
        for relative in relative_paths
    }
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return digest, files


def _native_config(
    repository: Path, script_path: Path, executable: Path, run_id: str,
    yaw_degrees: float, cache_path: Path,
) -> tuple[bytes, dict[str, Any]]:
    executable_hash = sha256_file(executable)
    source_hash, source_files = _source_manifest(repository, script_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
        text=True, capture_output=True,
    ).stdout.strip()
    if head != TASK_START_HEAD:
        raise HartleyH6Error("H6 execution HEAD moved from the frozen task-start HEAD")
    values: list[tuple[str, str]] = [
        ("run_id", run_id), ("backend_id", BACKEND_ID),
        ("process_policy", "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61"),
        ("sigma_fk_m", "0.010"), ("expected_records", str(STATE_ROWS)),
        ("cache_sha256", CACHE_SHA256), ("code_commit", head),
        ("task_start_head", TASK_START_HEAD), ("task_start_dirty_or_precommit", "true"),
        ("scoped_source_manifest_sha256", source_hash),
        ("native_executable_sha256", executable_hash),
        ("later_final_commit_mapping", "NOT_AVAILABLE_PRECOMMIT"),
        ("execution_phase", "H6_GAUGE_ENSEMBLE"),
        ("initial_gauge_yaw_deg", format(yaw_degrees, ".1f")),
    ]
    base = "".join(f"{key}={value}\n" for key, value in values)
    config_hash = hashlib.sha256(base.encode()).hexdigest()
    metadata = dict(values)
    metadata.update({
        "config_hash": config_hash, "cache_path": str(cache_path),
        "scoped_source_files": source_files,
    })
    return (base + f"config_hash={config_hash}\n").encode(), metadata


def _convert_covariance(binary: Path, destination: Path) -> None:
    arrays: dict[str, np.ndarray] = {}
    with binary.open("rb") as handle:
        index = 0
        while header := handle.read(4):
            if len(header) != 4:
                raise HartleyH6Error("truncated covariance checkpoint header")
            dimension = struct.unpack("<I", header)[0]
            payload = handle.read(dimension * dimension * 8)
            if len(payload) != dimension * dimension * 8:
                raise HartleyH6Error("truncated covariance checkpoint matrix")
            arrays[f"covariance_{index}"] = np.frombuffer(payload, dtype="<f8").reshape(
                (dimension, dimension), order="F"
            ).copy()
            index += 1
    if not arrays or destination.exists():
        raise HartleyH6Error("covariance conversion destination/input contract failed")
    np.savez(destination, **arrays)
    with np.load(destination, allow_pickle=False) as archive:
        if archive.files != list(arrays) or any(not np.array_equal(archive[key], value) for key, value in arrays.items()):
            raise HartleyH6Error("covariance NPZ conversion parity failed")
    binary.unlink()


def execute_raw_member(
    repository: Path, script_path: Path, scratch: Path, executable: Path,
    cache_path: Path, run_id: str, yaw_degrees: float,
) -> tuple[Path, dict[str, Any]]:
    if run_id not in (*YAW_BY_RUN_ID, PARITY_RUN_ID):
        raise HartleyH6Error("unknown H6 gauge identity")
    if run_id != PARITY_RUN_ID and YAW_BY_RUN_ID[run_id] != yaw_degrees:
        raise HartleyH6Error("H6 run/yaw identity mismatch")
    if run_id == PARITY_RUN_ID and yaw_degrees != 0.0:
        raise HartleyH6Error("parity replay must be exactly zero degrees")
    if sha256_file(cache_path) != CACHE_SHA256:
        raise HartleyH6Error("provider cache changed before native launch")
    raw_parent = scratch / "01_NATIVE_RAW"
    raw_parent.mkdir(exist_ok=True)
    output = raw_parent / run_id
    output.mkdir(exist_ok=False)
    config_bytes, metadata = _native_config(repository, script_path, executable, run_id, yaw_degrees, cache_path)
    exclusive_write(output / "NATIVE_CONFIG.cfg", config_bytes)
    environment = dict(os.environ)
    environment.update({key: "1" for key in THREAD_KEYS})
    started = time.monotonic()
    completed = subprocess.run(
        [str(executable.resolve(strict=True)), str(cache_path.resolve(strict=True)),
         str((output / "NATIVE_CONFIG.cfg").resolve(strict=True)), str(output.resolve(strict=True))],
        cwd=repository, env=environment, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        raise HartleyH6Error(f"native {run_id} failed: {completed.stderr[-2000:]}")
    if sha256_file(executable) != metadata["native_executable_sha256"]:
        raise HartleyH6Error("H6 native executable changed across launch")
    _convert_covariance(output / "COVARIANCE_CHECKPOINTS.bin", output / "COVARIANCE_CHECKPOINTS.npz")
    summary = json.loads((output / "NATIVE_SUMMARY.json").read_text())
    required = {
        "state_rows": STATE_ROWS, "propagation_calls": PROPAGATION_CALLS,
        "eq61_calls": PROPAGATION_CALLS, "eq52_calls": 0,
        "reference_open_count": 0, "trace_open_count": 0,
        "forbidden_value_decode_count": 0, "old_runtime_input_count": 0,
        "initial_gauge_yaw_deg": yaw_degrees,
    }
    mismatch = {key: (summary.get(key), value) for key, value in required.items() if summary.get(key) != value}
    if mismatch:
        raise HartleyH6Error(f"native H6 summary gate mismatch: {mismatch}")
    metadata.update({
        "launcher_wall_seconds": elapsed, "native_stdout": completed.stdout.strip(),
        "native_stderr": completed.stderr.strip(),
    })
    return output, metadata


def _canonical_covariance_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with np.load(path, allow_pickle=False) as archive:
        for key in archive.files:
            array = np.asarray(archive[key], dtype="<f8", order="C")
            digest.update(key.encode() + b"\0")
            digest.update(np.asarray(array.shape, dtype="<i8").tobytes())
            digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def scientific_digest(directory: Path) -> dict[str, Any]:
    exact_files = (
        "NAV.csv", "COVARIANCE_DIAGONALS.csv", "CONTACT_STATE.csv",
        "CONTACT_EVENT_LEDGER.csv", "KINEMATIC_INNOVATIONS.csv",
        "NIS_DIAGNOSTICS.csv", "COVARIANCE_CHECKPOINT_INDEX.csv",
        "EXECUTION_LEDGER.csv",
    )
    identities = {name: sha256_file(directory / name) for name in exact_files}
    identities["COVARIANCE_CHECKPOINTS.canonical"] = _canonical_covariance_digest(
        directory / "COVARIANCE_CHECKPOINTS.npz"
    )
    digest = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"digest": digest, "identities": identities}


def run_zero_parity(
    repository: Path, script_path: Path, scratch: Path, executable: Path,
    cache_path: Path, h5_anchor: Path, h5_external_anchor: Path,
) -> dict[str, Any]:
    evidence = scratch / "00_ADMIN" / "H6_ZERO_DEGREE_RUNNER_PARITY.json"
    if evidence.exists():
        parsed = json.loads(evidence.read_text())
        if parsed.get("parity_pass") is not True:
            raise HartleyH6Error("BLOCKED_LSE01_H6_ZERO_REPLAY_PARITY_FAILURE")
        return parsed
    local_freeze = json.loads((h5_anchor / "NATIVE_FREEZE.json").read_text())
    external_freeze = json.loads((h5_external_anchor / "NATIVE_FREEZE.json").read_text())
    if local_freeze.get("files") != external_freeze.get("files"):
        raise HartleyH6Error("local V3 H5 primary is not the authoritative G-stage mirror")
    replay, metadata = execute_raw_member(
        repository, script_path, scratch, executable, cache_path, PARITY_RUN_ID, 0.0
    )
    anchor_digest = scientific_digest(h5_anchor)
    replay_digest = scientific_digest(replay)
    exact_names = tuple(anchor_digest["identities"])
    exact_equal = {
        name: anchor_digest["identities"][name] == replay_digest["identities"][name]
        for name in exact_names
    }
    anchor_nav = _rows(h5_anchor / "NAV.csv")
    replay_nav = _rows(replay / "NAV.csv")
    checkpoint_equal = True
    with np.load(h5_anchor / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False) as left, np.load(
        replay / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False
    ) as right:
        checkpoint_equal = left.files == right.files and all(np.array_equal(left[key], right[key]) for key in left.files)
    payload = {
        "schema_version": "hartley.h6.zero_runner_parity.v1",
        "run_id": PARITY_RUN_ID, "zero_degree_replay_count": 1,
        "h5_primary_anchor_reused": True,
        "h5_local_anchor": str(h5_anchor), "h5_external_anchor": str(h5_external_anchor),
        "h5_local_external_freeze_identity_equal": True,
        "state_row_count_anchor": len(anchor_nav), "state_row_count_replay": len(replay_nav),
        "state_rows_identical": exact_equal["NAV.csv"],
        "contact_event_ledger_identical": exact_equal["CONTACT_EVENT_LEDGER.csv"],
        "contact_state_identical": exact_equal["CONTACT_STATE.csv"],
        "final_state_identical": anchor_nav[-1] == replay_nav[-1],
        "nis_stream_identical": exact_equal["NIS_DIAGNOSTICS.csv"],
        "innovation_stream_identical": exact_equal["KINEMATIC_INNOVATIONS.csv"],
        "covariance_checkpoint_index_identical": exact_equal["COVARIANCE_CHECKPOINT_INDEX.csv"],
        "covariance_checkpoint_arrays_identical": checkpoint_equal,
        "native_scientific_digest_anchor": anchor_digest["digest"],
        "native_scientific_digest_replay": replay_digest["digest"],
        "native_scientific_digest_identical": anchor_digest["digest"] == replay_digest["digest"],
        "scientific_file_equal": exact_equal,
        "serialization_tolerance": "EXACT_CSV_AND_CANONICAL_FLOAT64_ARRAY_BYTES",
        "reference_open_count": 0, "trace_open_count": 0,
        "replay_config_sha256": sha256_file(replay / "NATIVE_CONFIG.cfg"),
        "native_executable_sha256": metadata["native_executable_sha256"],
    }
    payload["parity_pass"] = all((
        payload["state_row_count_anchor"] == STATE_ROWS,
        payload["state_row_count_replay"] == STATE_ROWS,
        payload["state_rows_identical"], payload["contact_event_ledger_identical"],
        payload["contact_state_identical"], payload["final_state_identical"],
        payload["nis_stream_identical"], payload["innovation_stream_identical"],
        payload["covariance_checkpoint_index_identical"],
        payload["covariance_checkpoint_arrays_identical"],
        payload["native_scientific_digest_identical"],
    ))
    exclusive_json(evidence, payload)
    exclusive_write(
        scratch / "00_ADMIN" / "H6_ZERO_DEGREE_RUNNER_PARITY.sha256",
        (sha256_file(evidence) + "  H6_ZERO_DEGREE_RUNNER_PARITY.json\n").encode(),
    )
    _safe_remove_tree(replay, scratch / "01_NATIVE_RAW")
    if not payload["parity_pass"]:
        raise HartleyH6Error("BLOCKED_LSE01_H6_ZERO_REPLAY_PARITY_FAILURE")
    return payload


def freeze_tolerance_registry(scratch: Path) -> dict[str, Any]:
    contracts = scratch / "03_ANALYSIS" / "00_CONTRACTS"
    contracts.mkdir(parents=True, exist_ok=True)
    path = contracts / "H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text())
    parity_path = scratch / "00_ADMIN" / "H6_ZERO_DEGREE_RUNNER_PARITY.json"
    parity = json.loads(parity_path.read_text())
    if parity.get("parity_pass") is not True:
        raise HartleyH6Error("tolerance registry requires passed zero-degree replay")
    raw_parent = scratch / "01_NATIVE_RAW"
    frozen_parent = scratch / "02_FROZEN_RUNS"
    if any((raw_parent / run_id).exists() for run_id in YAW_BY_RUN_ID) or any(
        (frozen_parent / run_id).exists() for run_id in YAW_BY_RUN_ID
    ):
        raise HartleyH6Error("nonzero-yaw result existed before tolerance freeze")
    payload = {
        "schema_version": "hartley.h6.gauge_numerical_tolerance.v1",
        "frozen_before_nonzero_yaw_execution": True,
        "source_inputs": {
            "h3_h4_synthetic_normal_max_state_error": 2.8053536886893828e-12,
            "h3_h4_synthetic_stress_max_state_error": 1.0242440762170271e-9,
            "h3_h4_synthetic_stress_covariance_relative_error": 2.157093619136404e-8,
            "zero_degree_replay_floor": 0.0,
            "ieee754_float64_epsilon": float(np.finfo(float).eps),
            "sequence_length": STATE_ROWS,
            "state_magnitude_scale_policy": "finite_long_sequence_roundoff_and_large_world_state_guard",
        },
        "derivation": {
            "policy": "conservative_finite_preregistered_envelope",
            "nonzero_yaw_results_used": False, "reference_or_trace_used": False,
            "may_be_redefined_after_execution": False,
        },
        "metric_tolerances": {
            "orientation_geodesic_difference_rad": 2.0e-6,
            "velocity_difference_m_per_s": 2.0e-5,
            "position_difference_m": 5.0e-4,
            "contact_position_difference_m": 5.0e-4,
            "gyro_bias_difference_rad_per_s": 2.0e-6,
            "accelerometer_bias_difference_m_per_s2": 2.0e-6,
            "relative_yaw_increment_difference_rad": 2.0e-6,
            "innovation_norm_difference": 5.0e-5,
            "covariance_congruence_relative_frobenius_difference": 5.0e-5,
            "native_yaw_offset_residual_rad": 2.0e-6,
        },
    }
    data = yaml.safe_dump(payload, sort_keys=False).encode()
    registry_hash = exclusive_write(path, data)
    exclusive_json(
        contracts / "H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY_FREEZE.json",
        {"schema_version": "hartley.h6.tolerance_freeze.v1", "path": path.name,
         "sha256": registry_hash, "nonzero_yaw_run_count_at_freeze": 0,
         "reference_open_count": 0, "trace_open_count": 0},
    )
    return payload


def exclusive_csv_stream(
    path: Path, rows: Iterable[Mapping[str, Any]], columns: Sequence[str]
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="", closefd=True) as handle:
            class HashingWriter:
                def write(self, value: str) -> int:
                    digest.update(value.encode())
                    return handle.write(value)

            writer = csv.DictWriter(HashingWriter(), fieldnames=tuple(columns), lineterminator="\n")
            writer.writeheader()
            for source in rows:
                encoded: dict[str, Any] = {}
                for column in columns:
                    value = source.get(column, "")
                    if isinstance(value, (float, np.floating)):
                        value = format(float(value), ".17g")
                    elif isinstance(value, (bool, np.bool_)):
                        value = "true" if bool(value) else "false"
                    encoded[column] = value
                writer.writerow(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        raise
    return digest.hexdigest()


def _load_tolerances(scratch: Path) -> dict[str, float]:
    path = scratch / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml"
    freeze = scratch / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY_FREEZE.json"
    if not path.is_file() or not freeze.is_file():
        raise HartleyH6Error("nonzero member requires frozen tolerance registry")
    identity = json.loads(freeze.read_text())
    if sha256_file(path) != identity.get("sha256") or identity.get("nonzero_yaw_run_count_at_freeze") != 0:
        raise HartleyH6Error("tolerance registry freeze identity mismatch")
    return {key: float(value) for key, value in yaml.safe_load(path.read_text())["metric_tolerances"].items()}


def _checkpoint_rows(path: Path) -> list[dict[str, str]]:
    rows = _rows(path)
    for expected, row in enumerate(rows):
        if int(row["checkpoint_index"]) != expected or row["npz_key"] != f"covariance_{expected}":
            raise HartleyH6Error("checkpoint index/key contract mismatch")
    return rows


def compute_member_metrics(
    raw: Path, h5_anchor: Path, cache: CacheArrays, yaw_degrees: float,
    tolerances: Mapping[str, float],
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]], dict[str, Any]]:
    anchor = read_nav(h5_anchor / "NAV.csv")
    member = read_nav(raw / "NAV.csv")
    if not np.array_equal(anchor.timestamp_ns, member.timestamp_ns) or not np.array_equal(
        anchor.state_dimension, member.state_dimension
    ):
        raise HartleyH6Error("BLOCKED_LSE01_H6_CONTACT_EVENT_IDENTITY_MISMATCH")
    anchor_active, anchor_contacts = read_contact_state(h5_anchor / "CONTACT_STATE.csv")
    member_active, member_contacts = read_contact_state(raw / "CONTACT_STATE.csv")
    if not np.array_equal(anchor_active, member_active):
        raise HartleyH6Error("BLOCKED_LSE01_H6_CONTACT_EVENT_IDENTITY_MISMATCH")
    if sha256_file(raw / "CONTACT_EVENT_LEDGER.csv") != sha256_file(h5_anchor / "CONTACT_EVENT_LEDGER.csv"):
        raise HartleyH6Error("BLOCKED_LSE01_H6_CONTACT_EVENT_IDENTITY_MISMATCH")
    q = rotation_z(yaw_degrees)
    aligned_rotation = np.einsum("ij,njk->nik", q.T, member.rotation)
    relative = np.einsum("nji,njk->nik", anchor.rotation, aligned_rotation)
    cosine = np.clip((np.trace(relative, axis1=1, axis2=2) - 1.0) * 0.5, -1.0, 1.0)
    orientation = np.arccos(cosine)
    aligned_velocity = np.einsum("ij,nj->ni", q.T, member.velocity)
    aligned_position = np.einsum("ij,nj->ni", q.T, member.position)
    velocity = np.linalg.norm(aligned_velocity - anchor.velocity, axis=1)
    position = np.linalg.norm(aligned_position - anchor.position, axis=1)
    gyro_bias = np.linalg.norm(member.gyro_bias - anchor.gyro_bias, axis=1)
    accel_bias = np.linalg.norm(member.accel_bias - anchor.accel_bias, axis=1)
    aligned_contacts = np.einsum("ij,nlj->nli", q.T, member_contacts)
    contact = np.zeros(STATE_ROWS)
    for index in range(STATE_ROWS):
        active_ids = np.flatnonzero(anchor_active[index])
        if active_ids.size:
            contact[index] = float(np.max(np.linalg.norm(
                aligned_contacts[index, active_ids] - anchor_contacts[index, active_ids], axis=1
            )))
    anchor_innovation = innovation_norms(h5_anchor / "KINEMATIC_INNOVATIONS.csv")
    member_innovation = innovation_norms(raw / "KINEMATIC_INNOVATIONS.csv")
    innovation = np.abs(member_innovation - anchor_innovation)
    yaw_anchor = np.unwrap(np.arctan2(anchor.rotation[:, 1, 0], anchor.rotation[:, 0, 0]))
    yaw_member = np.unwrap(np.arctan2(member.rotation[:, 1, 0], member.rotation[:, 0, 0]))
    relative_yaw = np.abs(wrap_pi((yaw_member - yaw_member[0]) - (yaw_anchor - yaw_anchor[0])))
    native_offset = wrap_pi(yaw_member - yaw_anchor)
    expected_offset = -math.radians(yaw_degrees)
    native_offset_residual = np.abs(wrap_pi(native_offset - expected_offset))

    anchor_index = _checkpoint_rows(h5_anchor / "COVARIANCE_CHECKPOINT_INDEX.csv")
    member_index = _checkpoint_rows(raw / "COVARIANCE_CHECKPOINT_INDEX.csv")
    if anchor_index != member_index:
        raise HartleyH6Error("BLOCKED_LSE01_H6_CONTACT_EVENT_IDENTITY_MISMATCH")
    checkpoint_rows: list[dict[str, Any]] = []
    with np.load(h5_anchor / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False) as base_archive, np.load(
        raw / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False
    ) as member_archive:
        if base_archive.files != member_archive.files:
            raise HartleyH6Error("checkpoint key identity mismatch")
        for index, row in enumerate(anchor_index):
            key = row["npz_key"]
            left, right = base_archive[key], member_archive[key]
            dimension = int(row["dimension"])
            if left.shape != right.shape or left.shape != (dimension, dimension):
                raise HartleyH6Error("checkpoint covariance dimension mismatch")
            transform = np.eye(dimension)
            for offset in range(0, dimension - 6, 3):
                transform[offset:offset + 3, offset:offset + 3] = q
            aligned = transform.T @ right @ transform
            difference = float(np.linalg.norm(aligned - left) / max(1.0, np.linalg.norm(left)))
            checkpoint_rows.append({
                "run_id": raw.name, "initial_yaw_deg": yaw_degrees,
                "checkpoint_index": index, "row_index": int(row["row_index"]),
                "timestamp_ns": int(row["timestamp_ns"]), "reason": row["reason"],
                "contact_set": row["topology"], "dimension": dimension,
                "covariance_congruence_relative_frobenius_difference": difference,
                "tolerance": tolerances["covariance_congruence_relative_frobenius_difference"],
                "pass": difference <= tolerances["covariance_congruence_relative_frobenius_difference"],
            })

    metrics = {
        "timestamp_ns": anchor.timestamp_ns,
        "orientation_geodesic_difference_rad": orientation,
        "velocity_difference_m_per_s": velocity,
        "position_difference_m": position,
        "maximum_matched_contact_position_difference_m": contact,
        "gyro_bias_difference_rad_per_s": gyro_bias,
        "accelerometer_bias_difference_m_per_s2": accel_bias,
        "relative_yaw_increment_difference_rad": relative_yaw,
        "innovation_norm_difference": innovation,
        "native_yaw_offset_rad": np.asarray(native_offset),
        "native_yaw_offset_residual_rad": native_offset_residual,
    }
    pass_checks = {
        "orientation": float(np.max(orientation)) <= tolerances["orientation_geodesic_difference_rad"],
        "velocity": float(np.max(velocity)) <= tolerances["velocity_difference_m_per_s"],
        "position": float(np.max(position)) <= tolerances["position_difference_m"],
        "contact": float(np.max(contact)) <= tolerances["contact_position_difference_m"],
        "gyro_bias": float(np.max(gyro_bias)) <= tolerances["gyro_bias_difference_rad_per_s"],
        "accelerometer_bias": float(np.max(accel_bias)) <= tolerances["accelerometer_bias_difference_m_per_s2"],
        "relative_yaw": float(np.max(relative_yaw)) <= tolerances["relative_yaw_increment_difference_rad"],
        "innovation": float(np.max(innovation)) <= tolerances["innovation_norm_difference"],
        "native_yaw_offset": float(np.max(native_offset_residual)) <= tolerances["native_yaw_offset_residual_rad"],
        "covariance": all(row["pass"] for row in checkpoint_rows),
    }
    identity = {
        "contact_event_ledger_identical": True,
        "contact_identity_set_and_dimension_match_every_epoch": True,
        "pass_checks": pass_checks, "pass": all(pass_checks.values()),
    }
    return metrics, checkpoint_rows, identity


def compact_member(
    scratch: Path, raw: Path, h5_anchor: Path, cache_path: Path,
    metadata: Mapping[str, Any], yaw_degrees: float,
) -> dict[str, Any]:
    tolerances = _load_tolerances(scratch)
    cache = read_cache(cache_path)
    metrics, checkpoint_metrics, identity = compute_member_metrics(
        raw, h5_anchor, cache, yaw_degrees, tolerances
    )
    final_parent = scratch / "02_FROZEN_RUNS"
    final_parent.mkdir(exist_ok=True)
    final = final_parent / raw.name
    final.mkdir(exist_ok=False)
    copy_exclusive(raw / "NAV.csv", final / "NAV.csv")
    covariance_rows = _rows(raw / "COVARIANCE_DIAGONALS.csv")
    exclusive_csv(final / "GAUGE_COVARIANCE_DIAGONALS.csv", covariance_rows, H6_COVARIANCE_COLUMNS)
    copy_exclusive(raw / "COVARIANCE_CHECKPOINT_INDEX.csv", final / "COVARIANCE_CHECKPOINT_INDEX.csv")
    copy_exclusive(raw / "COVARIANCE_CHECKPOINTS.npz", final / "COVARIANCE_CHECKPOINTS.npz")
    nis_rows = _rows(raw / "NIS_DIAGNOSTICS.csv")
    if len(nis_rows) != STATE_ROWS:
        raise HartleyH6Error("native NIS epoch row count mismatch")
    norms = innovation_norms(raw / "KINEMATIC_INNOVATIONS.csv")

    def norm_rows() -> Iterator[dict[str, Any]]:
        for index, (timestamp, row) in enumerate(zip(cache.timestamp_ns, nis_rows)):
            survivor_mask = int(cache.contact_mask[index] & ~cache.add_mask[index]) if index else 0
            count = survivor_mask.bit_count()
            if int(row["contact_count"]) != count:
                raise HartleyH6Error("native survivor-contact NIS DoF identity mismatch")
            yield {
                "timestamp_ns": int(timestamp), "row_index": index,
                "contact_set": contact_set(survivor_mask), "contact_count": count,
                "stacked_innovation_norm": norms[index], "nis": float(row["nis"]),
                "factorization_success": row["factorization_ok"] == "1",
            }

    exclusive_csv_stream(final / "GAUGE_INNOVATION_NORMS.csv", norm_rows(), INNOVATION_NORM_COLUMNS)
    config_payload = {
        "schema_version": "hartley.h6.native_config.v1", "run_id": raw.name,
        "method_id": METHOD_ID, "backend_id": BACKEND_ID,
        "process_profile": PROCESS_PROFILE, "sigma_fk_m": SIGMA_FK_M,
        "initial_gauge_yaw_deg": yaw_degrees,
        "gauge_axis": "NORMALIZED_WORLD_GRAVITY_NEGATIVE_Z",
        "expected_native_euler_yaw_offset_deg": -yaw_degrees,
        "left_multiplication": True,
        "raw_sha256": RAW_SHA256, "complete_prefix_sha256": PREFIX_SHA256,
        "provider_cache_sha256": CACHE_SHA256,
        "contact_event_input_ledger_sha256": EVENT_LEDGER_SHA256,
        "threads": {key: 1 for key in THREAD_KEYS},
        "chronological_single_sequence": True, "epoch_parallelism": 1,
        "native_config_metadata": dict(metadata),
        "reference_open_count": 0, "trace_open_count": 0,
        "GNSS_input_count": 0, "Go2_onboard_pose_or_yaw_input_count": 0,
        "LegSA_output_input_count": 0, "EXT_output_input_count": 0,
    }
    exclusive_write(final / "NATIVE_CONFIG.yaml", yaml.safe_dump(config_payload, sort_keys=False).encode())
    raw_summary = json.loads((raw / "NATIVE_SUMMARY.json").read_text())
    summary = {
        **raw_summary, "schema_version": "hartley.h6.native_summary.v1",
        "provider_cache_referenced_not_duplicated": True,
        "provider_cache_sha256": CACHE_SHA256,
        "contact_event_input_ledger_referenced_not_duplicated": True,
        "contact_event_input_ledger_sha256": EVENT_LEDGER_SHA256,
        "h5_native_contact_event_output_sha256": sha256_file(h5_anchor / "CONTACT_EVENT_LEDGER.csv"),
        "h5_primary_anchor_reused": True,
        "contact_state_csv_published": False,
        "contact_event_ledger_csv_published": False,
        "full_per_contact_innovation_csv_published": False,
        "compact_stacked_innovation_norm_stream_published": True,
        "gauge_equivalence_pass": identity["pass"],
        "contact_identity_set_and_dimension_match_every_epoch": True,
        "reference_open_count": 0, "trace_open_count": 0,
        "GNSS_input_count": 0, "Go2_onboard_pose_or_yaw_input_count": 0,
        "LegSA_output_input_count": 0, "EXT_output_input_count": 0,
    }
    exclusive_json(final / "NATIVE_SUMMARY.json", summary)
    copy_exclusive(raw / "RUNTIME.csv", final / "RUNTIME.csv")
    metrics_parent = scratch / "03_ANALYSIS" / "08_EQUIVALENCE_MEMBER"
    metrics_parent.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_parent / f"{raw.name}.npz"
    if metrics_path.exists():
        raise HartleyH6Error("member equivalence metric payload already exists")
    np.savez_compressed(metrics_path, **metrics)
    checkpoint_path = metrics_parent / f"{raw.name}_CHECKPOINTS.csv"
    checkpoint_columns = tuple(checkpoint_metrics[0])
    exclusive_csv(checkpoint_path, checkpoint_metrics, checkpoint_columns)
    exclusive_json(metrics_parent / f"{raw.name}_IDENTITY.json", identity)
    files = {
        name: {"size": (final / name).stat().st_size, "sha256": sha256_file(final / name)}
        for name in COMPACT_RUN_FILES
    }
    freeze = {
        "schema_version": "hartley.h6.native_freeze.v1", "run_id": raw.name,
        "initial_gauge_yaw_deg": yaw_degrees, "files": files,
        "state_rows": STATE_ROWS, "reference_open_count": 0, "trace_open_count": 0,
        "contact_state_csv_duplicated": False, "provider_cache_duplicated": False,
        "contact_event_ledger_duplicated": False, "full_innovation_csv_duplicated": False,
    }
    exclusive_json(final / "NATIVE_FREEZE.json", freeze)
    for name, expected in files.items():
        if sha256_file(final / name) != expected["sha256"] or (final / name).stat().st_size != expected["size"]:
            raise HartleyH6Error("native compact freeze self-verification failed")
    _safe_remove_tree(raw, scratch / "01_NATIVE_RAW")
    if not identity["pass"]:
        raise HartleyH6Error("BLOCKED_LSE01_H6_GAUGE_EQUIVARIANCE_FAILURE")
    return {"run_id": final.name, "yaw_degrees": yaw_degrees, "final": str(final), **identity}


def run_member(
    repository: Path, script_path: Path, scratch: Path, executable: Path,
    cache_path: Path, h5_anchor: Path, run_id: str,
) -> dict[str, Any]:
    yaw_degrees = YAW_BY_RUN_ID[run_id]
    raw, metadata = execute_raw_member(
        repository, script_path, scratch, executable, cache_path, run_id, yaw_degrees
    )
    return compact_member(scratch, raw, h5_anchor, cache_path, metadata, yaw_degrees)


EPOCH_METRIC_COLUMNS = (
    "run_id", "initial_yaw_deg", "row_index", "timestamp_ns",
    "orientation_geodesic_difference_rad", "velocity_difference_m_per_s",
    "position_difference_m", "maximum_matched_contact_position_difference_m",
    "gyro_bias_difference_rad_per_s", "accelerometer_bias_difference_m_per_s2",
    "relative_yaw_increment_difference_rad", "innovation_norm_difference",
    "native_yaw_offset_rad", "native_yaw_offset_residual_rad", "epoch_pass",
)


def _epoch_metric_rows_from_cached_arrays(
    run_id: str, yaw_degrees: float, arrays: Mapping[str, np.ndarray],
    tolerances: Mapping[str, float], metric_map: Mapping[str, str],
) -> Iterator[dict[str, Any]]:
    """Emit the preregistered rows after each compressed array is loaded once."""
    for index in range(STATE_ROWS):
        passed = all(
            float(arrays[metric][index]) <= tolerances[tolerance]
            for metric, tolerance in metric_map.items()
        )
        yield {
            "run_id": run_id, "initial_yaw_deg": yaw_degrees, "row_index": index,
            **{name: arrays[name][index] for name in EPOCH_METRIC_COLUMNS if name in arrays},
            "epoch_pass": passed,
        }


def aggregate_equivalence(scratch: Path) -> dict[str, Any]:
    output = scratch / "03_ANALYSIS" / "08_EQUIVALENCE"
    output.mkdir(parents=True, exist_ok=False)
    tolerances = _load_tolerances(scratch)
    member_root = scratch / "03_ANALYSIS" / "08_EQUIVALENCE_MEMBER"
    metric_map = {
        "orientation_geodesic_difference_rad": "orientation_geodesic_difference_rad",
        "velocity_difference_m_per_s": "velocity_difference_m_per_s",
        "position_difference_m": "position_difference_m",
        "maximum_matched_contact_position_difference_m": "contact_position_difference_m",
        "gyro_bias_difference_rad_per_s": "gyro_bias_difference_rad_per_s",
        "accelerometer_bias_difference_m_per_s2": "accelerometer_bias_difference_m_per_s2",
        "relative_yaw_increment_difference_rad": "relative_yaw_increment_difference_rad",
        "innovation_norm_difference": "innovation_norm_difference",
        "native_yaw_offset_residual_rad": "native_yaw_offset_residual_rad",
    }

    def epoch_rows() -> Iterator[dict[str, Any]]:
        for run_id, yaw, _ in YAW_MEMBERS:
            with np.load(member_root / f"{run_id}.npz", allow_pickle=False) as archive:
                arrays = {name: archive[name] for name in archive.files}
            yield from _epoch_metric_rows_from_cached_arrays(
                run_id, yaw, arrays, tolerances, metric_map,
            )

    epoch_path = output / "GAUGE_EQUIVALENCE_EPOCH_METRICS.csv"
    exclusive_csv_stream(epoch_path, epoch_rows(), EPOCH_METRIC_COLUMNS)
    checkpoint_rows = [
        row for run_id, _, _ in YAW_MEMBERS
        for row in _rows(member_root / f"{run_id}_CHECKPOINTS.csv")
    ]
    checkpoint_columns = tuple(checkpoint_rows[0])
    checkpoint_path = output / "GAUGE_EQUIVALENCE_CHECKPOINT_METRICS.csv"
    exclusive_csv(checkpoint_path, checkpoint_rows, checkpoint_columns)
    summary_rows: list[dict[str, Any]] = []
    yaw_rows: list[dict[str, Any]] = []
    overall = True
    for run_id, yaw, _ in YAW_MEMBERS:
        with np.load(member_root / f"{run_id}.npz", allow_pickle=False) as archive:
            row: dict[str, Any] = {"run_id": run_id, "initial_yaw_deg": yaw, "state_rows": STATE_ROWS}
            passed = True
            for metric, tolerance_name in metric_map.items():
                values = archive[metric]
                for quantile, label in ((0.5, "p50"), (0.9, "p90"), (0.95, "p95"), (0.99, "p99")):
                    row[f"{metric}_{label}"] = float(np.quantile(values, quantile))
                row[f"{metric}_max"] = float(np.max(values))
                row[f"{metric}_tolerance"] = tolerances[tolerance_name]
                passed = passed and row[f"{metric}_max"] <= tolerances[tolerance_name]
            covariance_values = np.asarray([
                float(item["covariance_congruence_relative_frobenius_difference"])
                for item in checkpoint_rows if item["run_id"] == run_id
            ])
            row["covariance_congruence_relative_frobenius_difference_max"] = float(np.max(covariance_values))
            row["covariance_congruence_relative_frobenius_difference_tolerance"] = tolerances[
                "covariance_congruence_relative_frobenius_difference"
            ]
            passed = passed and row["covariance_congruence_relative_frobenius_difference_max"] <= row[
                "covariance_congruence_relative_frobenius_difference_tolerance"
            ]
            row["contact_event_ledger_identical"] = True
            row["contact_identity_set_and_dimension_match_every_epoch"] = True
            row["pass"] = passed
            overall = overall and passed
            summary_rows.append(row)
            offsets = archive["native_yaw_offset_rad"]
            residuals = archive["native_yaw_offset_residual_rad"]
            yaw_rows.append({
                "run_id": run_id, "initial_yaw_deg_about_normalized_gravity": yaw,
                "expected_conventional_euler_yaw_offset_deg": -yaw,
                "native_yaw_offset_circular_mean_rad": float(math.atan2(np.mean(np.sin(offsets)), np.mean(np.cos(offsets)))),
                "native_yaw_offset_residual_max_rad": float(np.max(residuals)),
                "native_yaw_offset_residual_p99_rad": float(np.quantile(residuals, 0.99)),
                "tolerance_rad": tolerances["native_yaw_offset_residual_rad"],
                "pass": float(np.max(residuals)) <= tolerances["native_yaw_offset_residual_rad"],
            })
    summary_columns = tuple(summary_rows[0])
    exclusive_csv(output / "GAUGE_EQUIVALENCE_SUMMARY.csv", summary_rows, summary_columns)
    exclusive_csv(output / "GAUGE_NATIVE_YAW_OFFSET_SUMMARY.csv", yaw_rows, tuple(yaw_rows[0]))
    result = {
        "schema_version": "hartley.h6.gauge_equivalence.v1",
        "nonzero_yaw_run_count": 6, "state_rows_per_run": STATE_ROWS,
        "checkpoint_rows": len(checkpoint_rows), "gauge_equivalence_pass": overall,
        "reference_open_count": 0, "trace_open_count": 0,
        "files": {
            path.name: {"size": path.stat().st_size, "sha256": sha256_file(path)}
            for path in output.iterdir() if path.is_file()
        },
    }
    exclusive_json(output / "GAUGE_EQUIVALENCE_FREEZE.json", result)
    if not overall:
        raise HartleyH6Error("BLOCKED_LSE01_H6_GAUGE_EQUIVARIANCE_FAILURE")
    return result


def _excitation_label(gyro_rms: float, accel_variability: float) -> str:
    if gyro_rms < 0.05 and accel_variability < 0.10:
        return "STATIC_LOW"
    score = math.hypot(gyro_rms, accel_variability)
    if score < 0.20:
        return "LOW"
    if score < 1.0:
        return "MODERATE"
    return "HIGH"


def enumerate_segments(cache: CacheArrays) -> list[Segment]:
    if len(cache.timestamp_ns) != STATE_ROWS:
        raise HartleyH6Error("segment inventory requires complete provider cache")
    boundaries = np.flatnonzero(np.r_[True, cache.contact_mask[1:] != cache.contact_mask[:-1], True])
    segments: list[Segment] = []
    for number, (start, stop) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        end = int(stop - 1)
        start = int(start)
        mask = int(cache.contact_mask[start])
        duration = (int(cache.timestamp_ns[end]) - int(cache.timestamp_ns[start])) * 1.0e-9
        gyro_rms = float(np.sqrt(np.mean(np.sum(cache.gyro[start:end + 1] ** 2, axis=1))))
        accel_variability = float(np.std(np.linalg.norm(cache.accel[start:end + 1], axis=1)))
        count = mask.bit_count()
        segments.append(Segment(
            segment_id=f"SEG{number:05d}", start_row=start, end_row=end,
            start_timestamp_ns=int(cache.timestamp_ns[start]),
            end_timestamp_ns=int(cache.timestamp_ns[end]), duration_seconds=duration,
            sample_count=end - start + 1, contact_mask=mask,
            contact_set=contact_set(mask), contact_count=count,
            gyro_rms_rad_per_s=gyro_rms,
            accelerometer_norm_variability_m_per_s2=accel_variability,
            input_excitation_score=math.hypot(gyro_rms, accel_variability),
            excitation_label=_excitation_label(gyro_rms, accel_variability),
            eligible=duration >= 0.20 and end - start + 1 >= 20 and count > 0,
        ))
    if sum(segment.sample_count for segment in segments) != STATE_ROWS:
        raise HartleyH6Error("segment inventory lost provider epochs")
    return segments


SEGMENT_COLUMNS = (
    "segment_id", "start_row", "end_row", "start_timestamp_ns", "end_timestamp_ns",
    "duration_seconds", "sample_count", "contact_mask", "contact_set", "contact_count",
    "gyro_rms_rad_per_s", "accelerometer_norm_variability_m_per_s2",
    "input_excitation_score", "excitation_label", "eligible",
    "constant_contact_identity_set", "constant_state_dimension",
    "contact_boundary_inside_segment", "segment_role",
)


def freeze_window_selection(scratch: Path, cache_path: Path) -> dict[str, Any]:
    root = scratch / "03_ANALYSIS" / "10_OBSERVABILITY"
    inventory_root = root / "00_SEGMENT_INVENTORY"
    selection_root = root / "01_WINDOW_SELECTION"
    inventory_root.mkdir(parents=True, exist_ok=False)
    selection_root.mkdir(parents=True, exist_ok=False)
    cache = read_cache(cache_path)
    segments = enumerate_segments(cache)
    inventory_rows = [{
        **asdict(segment), "constant_contact_identity_set": True,
        "constant_state_dimension": True, "contact_boundary_inside_segment": False,
        "segment_role": "PROPAGATION_ONLY_FLIGHT_DIAGNOSTIC" if segment.contact_count == 0 else "CONTACT_AIDED",
    } for segment in segments]
    inventory_path = inventory_root / "OBSERVABILITY_SEGMENT_INVENTORY.csv"
    exclusive_csv(inventory_path, inventory_rows, SEGMENT_COLUMNS)
    zero_rows = [row for row in inventory_rows if row["contact_count"] == 0]
    exclusive_csv(
        inventory_root / "ZERO_CONTACT_PROPAGATION_ONLY_SEGMENTS.csv", zero_rows, SEGMENT_COLUMNS
    )
    selected: dict[str, dict[str, Any]] = {}

    def add(segment: Segment, role: str) -> None:
        entry = selected.setdefault(segment.segment_id, {**asdict(segment), "selection_roles": []})
        entry["selection_roles"].append(role)

    available_counts: list[int] = []
    for count in range(1, 5):
        candidates = [segment for segment in segments if segment.contact_count == count and segment.eligible]
        if not candidates:
            continue
        available_counts.append(count)
        add(min(candidates, key=lambda item: (item.start_timestamp_ns, item.contact_set)), f"contact_count_{count}_earliest")
        add(min(candidates, key=lambda item: (-item.duration_seconds, item.start_timestamp_ns, item.contact_set)), f"contact_count_{count}_longest")
        add(min(candidates, key=lambda item: (-item.input_excitation_score, item.start_timestamp_ns, item.contact_set)), f"contact_count_{count}_highest_input_excitation")
    initial_four = segments[0] if segments and segments[0].contact_count == 4 and segments[0].eligible else None
    if initial_four is not None:
        add(initial_four, "fixed_initial_four_contact_static_window")
    selection_rows: list[dict[str, Any]] = []
    for number, entry in enumerate(sorted(selected.values(), key=lambda item: (item["start_timestamp_ns"], item["contact_set"]))):
        selection_rows.append({
            "window_id": f"WIN{number:03d}", "segment_id": entry["segment_id"],
            "selection_roles": ";".join(sorted(entry["selection_roles"])),
            **{key: entry[key] for key in (
                "start_row", "end_row", "start_timestamp_ns", "end_timestamp_ns",
                "duration_seconds", "sample_count", "contact_mask", "contact_set",
                "contact_count", "gyro_rms_rad_per_s",
                "accelerometer_norm_variability_m_per_s2", "input_excitation_score",
                "excitation_label",
            )},
            "constant_contact_identity_set": True, "constant_state_dimension": True,
            "contact_boundary_inside_window": False,
            "selection_used_singular_values_or_rank": False,
            "svd_call_count_before_freeze": 0,
        })
    if not selection_rows:
        raise HartleyH6Error("BLOCKED_LSE01_H6_OBSERVABILITY_WINDOW_CONTRACT_FAILURE")
    selection_columns = tuple(selection_rows[0])
    selection_path = selection_root / "H6_OBSERVABILITY_WINDOW_SELECTION.csv"
    selection_hash = exclusive_csv(selection_path, selection_rows, selection_columns)
    freeze = {
        "schema_version": "hartley.h6.observability_window_selection.v1",
        "selection_csv_sha256": selection_hash,
        "segment_inventory_sha256": sha256_file(inventory_path),
        "provider_cache_sha256": CACHE_SHA256,
        "selection_input_fields": ["timestamp_ns", "contact_mask", "gyro", "accelerometer"],
        "selection_forbidden_input_count": 0,
        "svd_call_count_before_freeze": 0,
        "rank_output_read_count_before_freeze": 0,
        "available_eligible_contact_counts": available_counts,
        "selected_window_count_after_role_deduplication": len(selection_rows),
        "initial_four_contact_static_window_included": initial_four is not None,
        "zero_contact_segment_count": len(zero_rows),
        "reference_open_count": 0, "trace_open_count": 0,
    }
    freeze_path = selection_root / "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json"
    exclusive_json(freeze_path, freeze)
    return freeze


def _skew(value: np.ndarray) -> np.ndarray:
    x, y, z = map(float, value)
    return np.asarray(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def _gamma_series(phi: np.ndarray, order: int) -> np.ndarray:
    matrix = _skew(phi)
    power = np.eye(3)
    denominator = float(math.factorial(order))
    result = power / denominator
    for n in range(1, 64):
        power = power @ matrix
        denominator *= n + order
        term = power / denominator
        result += term
        if np.max(np.abs(term)) < 2.0e-16:
            break
    return result


def _psi_series(phi: np.ndarray, vector: np.ndarray, order: int) -> np.ndarray:
    matrix = _skew(phi)
    powers = [np.eye(3)]
    for _ in range(1, 64):
        powers.append(powers[-1] @ matrix)
    result = np.zeros((3, 3))
    denominator = float(math.factorial(order))
    for n in range(1, 64):
        denominator *= n + order
        derivative = np.zeros((3, 3))
        for column in range(3):
            basis = np.zeros(3)
            basis[column] = 1.0
            d_power = sum((powers[k] @ _skew(basis) @ powers[n - 1 - k] for k in range(n)), np.zeros((3, 3)))
            derivative[:, column] = d_power @ vector
        term = derivative / denominator
        result += term
        if np.max(np.abs(term)) < 2.0e-16:
            break
    return result


def analytical_phi(
    rotation: np.ndarray, velocity: np.ndarray, position: np.ndarray,
    contacts: np.ndarray, corrected_omega: np.ndarray,
    corrected_acceleration: np.ndarray, dt: float,
) -> np.ndarray:
    count = len(contacts)
    dimension = 15 + 3 * count
    gyro_bias = dimension - 6
    accel_bias = dimension - 3
    phi = corrected_omega * dt
    g0, g1, g2 = (_gamma_series(phi, order) for order in (0, 1, 2))
    p1 = _psi_series(phi, corrected_acceleration, 1)
    p2 = _psi_series(phi, corrected_acceleration, 2)
    final_velocity = velocity + GRAVITY * dt + rotation @ g1 @ corrected_acceleration * dt
    final_position = (
        position + velocity * dt + 0.5 * GRAVITY * dt * dt
        + rotation @ g2 @ corrected_acceleration * dt * dt
    )
    rotation_bias = -rotation @ g1 * dt
    transition = np.eye(dimension)
    transition[0:3, gyro_bias:gyro_bias + 3] = rotation_bias
    transition[3:6, 0:3] = _skew(GRAVITY) * dt
    transition[3:6, gyro_bias:gyro_bias + 3] = (
        -rotation @ p1 * dt * dt + _skew(final_velocity) @ rotation_bias
    )
    transition[3:6, accel_bias:accel_bias + 3] = -rotation @ g1 * dt
    transition[6:9, 0:3] = 0.5 * _skew(GRAVITY) * dt * dt
    transition[6:9, 3:6] = np.eye(3) * dt
    transition[6:9, gyro_bias:gyro_bias + 3] = (
        -rotation @ p2 * dt * dt * dt + _skew(final_position) @ rotation_bias
    )
    transition[6:9, accel_bias:accel_bias + 3] = -rotation @ g2 * dt * dt
    for index, contact in enumerate(contacts):
        transition[9 + 3 * index:12 + 3 * index, gyro_bias:gyro_bias + 3] = _skew(contact) @ rotation_bias
    return transition


def measurement_matrix(contact_count: int, *, bias_augmented: bool) -> np.ndarray:
    dimension = (15 if bias_augmented else 9) + 3 * contact_count
    matrix = np.zeros((3 * contact_count, dimension))
    for index in range(contact_count):
        matrix[3 * index:3 * index + 3, 6:9] = -np.eye(3)
        matrix[3 * index:3 * index + 3, 9 + 3 * index:12 + 3 * index] = np.eye(3)
    return matrix


def gauge_basis(contact_count: int, *, bias_augmented: bool) -> np.ndarray:
    dimension = (15 if bias_augmented else 9) + 3 * contact_count
    basis = np.zeros((dimension, 4))
    basis[0:3, 0] = GRAVITY / np.linalg.norm(GRAVITY)
    for axis in range(3):
        basis[6 + axis, 1 + axis] = 1.0
        for index in range(contact_count):
            basis[9 + 3 * index + axis, 1 + axis] = 1.0
    return basis


def ideal_observability(times_seconds: np.ndarray, contact_count: int) -> np.ndarray:
    dimension = 9 + 3 * contact_count
    system = np.zeros((dimension, dimension))
    system[3:6, 0:3] = _skew(GRAVITY)
    system[6:9, 3:6] = np.eye(3)
    system2 = system @ system
    measurement = measurement_matrix(contact_count, bias_augmented=False)
    identity = np.eye(dimension)
    return np.vstack([
        measurement @ (identity + system * float(value) + 0.5 * system2 * float(value) ** 2)
        for value in times_seconds
    ])


def _observability_diagnostics(
    observability: np.ndarray, known_gauge: np.ndarray, multipliers: Sequence[float],
) -> tuple[list[dict[str, Any]], dict[str, Any], np.ndarray, np.ndarray]:
    _u, singular, vh = np.linalg.svd(observability, full_matrices=False)
    maximum = float(singular[0]) if singular.size else 0.0
    base_threshold = max(1.0e-12, 1.0e-9 * maximum)
    gauge_q, _ = np.linalg.qr(known_gauge)
    complement = null_space(gauge_q.T)
    nongauge_singular = np.linalg.svd(observability @ complement, compute_uv=False)
    rank_rows: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {
        "base_threshold": base_threshold,
        "o_times_g_normalized_residual": float(
            np.linalg.norm(observability @ known_gauge)
            / max(np.linalg.norm(observability, 2) * np.linalg.norm(known_gauge), np.finfo(float).tiny)
        ),
        "h_times_g_fro_residual": None,
        "smallest_non_gauge_singular_value": float(nongauge_singular[-1]),
        "condition_number_after_gauge_projection": float(nongauge_singular[0] / nongauge_singular[-1]),
    }
    for multiplier in multipliers:
        threshold = base_threshold * multiplier
        rank = int(np.sum(singular > threshold))
        nullity = observability.shape[1] - rank
        numerical_null = vh[rank:, :].T
        if numerical_null.shape[1]:
            projected = (np.eye(observability.shape[1]) - numerical_null @ numerical_null.T) @ gauge_q
            residual = float(np.linalg.norm(projected, 2))
            cosines = np.linalg.svd(gauge_q.T @ numerical_null, compute_uv=False)
            angles = np.arccos(np.clip(cosines, -1.0, 1.0))
            maximum_angle = float(np.max(angles)) if angles.size else math.pi / 2.0
        else:
            residual, maximum_angle = 1.0, math.pi / 2.0
        rank_rows.append({
            "tolerance_multiplier": multiplier, "threshold": threshold,
            "rank": rank, "nullity": nullity,
            "gauge_to_numerical_nullspace_residual": residual,
            "largest_known_gauge_principal_angle_rad": maximum_angle,
            "largest_known_gauge_principal_angle_deg": math.degrees(maximum_angle),
        })
    return rank_rows, diagnostics, singular, complement


def _selected_windows(scratch: Path) -> list[dict[str, str]]:
    root = scratch / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION"
    selection = root / "H6_OBSERVABILITY_WINDOW_SELECTION.csv"
    freeze = json.loads((root / "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json").read_text())
    if freeze.get("svd_call_count_before_freeze") != 0 or sha256_file(selection) != freeze.get("selection_csv_sha256"):
        raise HartleyH6Error("BLOCKED_LSE01_H6_OBSERVABILITY_WINDOW_CONTRACT_FAILURE")
    return _rows(selection)


def analyze_observability(
    scratch: Path, cache_path: Path, h5_anchor: Path,
) -> dict[str, Any]:
    windows = _selected_windows(scratch)
    cache = read_cache(cache_path)
    nav = read_nav(h5_anchor / "NAV.csv")
    active, contacts = read_contact_state(h5_anchor / "CONTACT_STATE.csv")
    ideal_root = scratch / "03_ANALYSIS/10_OBSERVABILITY/02_IDEAL_BIAS_FREE"
    bias_root = scratch / "03_ANALYSIS/10_OBSERVABILITY/03_BIAS_AUGMENTED"
    ideal_root.mkdir(parents=True, exist_ok=False)
    bias_root.mkdir(parents=True, exist_ok=False)
    singular_rows: list[dict[str, Any]] = []
    rank_rows: list[dict[str, Any]] = []
    weak_rows: list[dict[str, Any]] = []
    null_summary: dict[str, Any] = {
        "schema_version": "hartley.h6.observability_nullspace.v1",
        "known_gauge_basis": ["gravity_axis_rotation", "translation_x", "translation_y", "translation_z"],
        "ideal": [], "bias_augmented": [], "reference_open_count": 0, "trace_open_count": 0,
    }
    ideal_pass = True
    bias_gauge_pass = True
    for window in windows:
        start, end = int(window["start_row"]), int(window["end_row"])
        count = int(window["contact_count"])
        expected_mask = int(window["contact_mask"])
        if not np.all(cache.contact_mask[start:end + 1] == expected_mask):
            raise HartleyH6Error("BLOCKED_LSE01_H6_OBSERVABILITY_WINDOW_CONTRACT_FAILURE")
        times = (cache.timestamp_ns[start:end + 1] - cache.timestamp_ns[start]) * 1.0e-9
        ideal = ideal_observability(times, count)
        ideal_gauge = gauge_basis(count, bias_augmented=False)
        ideal_rank, ideal_diagnostics, ideal_singular, _ = _observability_diagnostics(
            ideal, ideal_gauge, (0.1, 1.0, 10.0)
        )
        expected_rank = 5 + 3 * count
        passed = (
            all(row["rank"] == expected_rank and row["nullity"] == 4 for row in ideal_rank)
            and ideal_diagnostics["o_times_g_normalized_residual"] <= 1.0e-9
            and max(row["gauge_to_numerical_nullspace_residual"] for row in ideal_rank) <= 1.0e-7
            and max(row["largest_known_gauge_principal_angle_deg"] for row in ideal_rank) <= 1.0e-5
        )
        ideal_pass = ideal_pass and passed
        null_summary["ideal"].append({
            "window_id": window["window_id"], "contact_count": count,
            "dimension": ideal.shape[1], "measurement_row_count": ideal.shape[0],
            "expected_rank": expected_rank, "expected_nullity": 4,
            **ideal_diagnostics, "rank_sensitivity_stable": all(row["rank"] == expected_rank for row in ideal_rank),
            "pass": passed,
        })
        for row in ideal_rank:
            rank_rows.append({"model": "IDEAL_BIAS_FREE", "window_id": window["window_id"], **row})
        for index, value in enumerate(ideal_singular):
            singular_rows.append({
                "model": "IDEAL_BIAS_FREE", "normalization": "RAW_STRUCTURAL",
                "window_id": window["window_id"], "singular_index_descending": index,
                "singular_value": float(value),
            })

        dimension = 15 + 3 * count
        measurement = measurement_matrix(count, bias_augmented=True)
        cumulative = np.eye(dimension)
        blocks = [measurement.copy()]
        active_ids = np.flatnonzero(active[start])
        if len(active_ids) != count or any(int(cache.contact_mask[index]) != expected_mask for index in range(start, end + 1)):
            raise HartleyH6Error("bias window topology mismatch")
        for index in range(start + 1, end + 1):
            previous = index - 1
            previous_ids = np.flatnonzero(active[previous])
            if not np.array_equal(previous_ids, active_ids):
                raise HartleyH6Error("bias window contact identity changed")
            dt = (int(cache.timestamp_ns[index]) - int(cache.timestamp_ns[previous])) * 1.0e-9
            step = analytical_phi(
                nav.rotation[previous], nav.velocity[previous], nav.position[previous],
                contacts[previous, active_ids], cache.gyro[previous] - nav.gyro_bias[previous],
                cache.accel[previous] - nav.accel_bias[previous], dt,
            )
            cumulative = step @ cumulative
            blocks.append(measurement @ cumulative)
        bias_observability = np.vstack(blocks)
        bias_gauge = gauge_basis(count, bias_augmented=True)
        bias_rank, bias_diagnostics, bias_singular, complement = _observability_diagnostics(
            bias_observability, bias_gauge, (0.1, 1.0, 10.0)
        )
        column_norm = np.linalg.norm(bias_observability, axis=0)
        normalized = bias_observability / np.where(column_norm > np.finfo(float).tiny, column_norm, 1.0)
        normalized_singular = np.linalg.svd(normalized, compute_uv=False)
        known_gauge_ok = (
            bias_diagnostics["o_times_g_normalized_residual"] <= 1.0e-9
            and max(row["gauge_to_numerical_nullspace_residual"] for row in bias_rank) <= 1.0e-7
            and max(row["largest_known_gauge_principal_angle_deg"] for row in bias_rank) <= 1.0e-5
        )
        bias_gauge_pass = bias_gauge_pass and known_gauge_ok
        structural = next(row for row in bias_rank if row["tolerance_multiplier"] == 1.0)
        null_summary["bias_augmented"].append({
            "window_id": window["window_id"], "contact_count": count,
            "dimension": dimension, "measurement_row_count": bias_observability.shape[0],
            "raw_rank": structural["rank"], "raw_nullity": structural["nullity"],
            "known_gauge_dimension": 4,
            "additional_numerical_nullity": max(0, structural["nullity"] - 4),
            "additional_nullity_called_gauge": False,
            "excitation_label": window["excitation_label"],
            **bias_diagnostics, "known_gauge_confirmed": known_gauge_ok,
        })
        for row in bias_rank:
            rank_rows.append({"model": "BIAS_AUGMENTED_REAL_TRAJECTORY", "window_id": window["window_id"], **row})
        for normalization, values in (("RAW_STRUCTURAL", bias_singular), ("COLUMN_NORMALIZED_DIAGNOSTIC_ONLY", normalized_singular)):
            for index, value in enumerate(values):
                singular_rows.append({
                    "model": "BIAS_AUGMENTED_REAL_TRAJECTORY", "normalization": normalization,
                    "window_id": window["window_id"], "singular_index_descending": index,
                    "singular_value": float(value),
                })
        projected = bias_observability @ complement
        _u, projected_singular, projected_vh = np.linalg.svd(projected, full_matrices=False)
        for weak_index in range(min(5, len(projected_singular))):
            source_index = len(projected_singular) - 1 - weak_index
            direction = complement @ projected_vh[source_index]
            bias_fraction = float(np.sum(direction[-6:] ** 2) / np.sum(direction ** 2))
            weak_rows.append({
                "window_id": window["window_id"], "weak_direction_index": weak_index,
                "non_gauge_singular_value": float(projected_singular[source_index]),
                "bias_energy_fraction": bias_fraction,
                "bias_dominated": bias_fraction >= 0.5,
                "direction_class": "BIAS_DOMINATED_WEAK" if bias_fraction >= 0.5 else "MIXED_OR_GROUP_STATE_WEAK",
                "excitation_label": window["excitation_label"],
                "called_additional_gauge": False,
            })
    singular_columns = tuple(singular_rows[0])
    rank_columns = tuple(rank_rows[0])
    exclusive_csv(ideal_root / "OBSERVABILITY_SINGULAR_VALUES.csv", singular_rows, singular_columns)
    exclusive_csv(ideal_root / "OBSERVABILITY_RANK_SENSITIVITY.csv", rank_rows, rank_columns)
    exclusive_json(ideal_root / "OBSERVABILITY_NULLSPACE_SUMMARY.json", null_summary)
    exclusive_csv(
        bias_root / "BIAS_AUGMENTED_WEAK_DIRECTION_SUMMARY.csv", weak_rows, tuple(weak_rows[0])
    )
    result = {
        "schema_version": "hartley.h6.observability.v1",
        "selected_window_count": len(windows), "ideal_observability_gauge_dimension": 4,
        "ideal_rank_nullity_pass": ideal_pass,
        "bias_augmented_known_gauge_confirmed": bias_gauge_pass,
        "reference_open_count": 0, "trace_open_count": 0,
    }
    exclusive_json(bias_root / "OBSERVABILITY_ANALYSIS_FREEZE.json", result)
    if not ideal_pass:
        raise HartleyH6Error("BLOCKED_LSE01_H6_IDEAL_NULLSPACE_FAILURE")
    if not bias_gauge_pass:
        raise HartleyH6Error("BLOCKED_LSE01_H6_KNOWN_GAUGE_NOT_IN_BIAS_AUGMENTED_NULLSPACE")
    return result


def _quantile(values: np.ndarray, probability: float) -> float | str:
    return float(np.quantile(values, probability)) if values.size else ""


def _nis_summary_row(
    group_type: str, group_id: str, contact_count_value: int,
    indices: np.ndarray, nis: np.ndarray, factorization: np.ndarray,
) -> dict[str, Any]:
    values = nis[indices]
    dof = 3 * contact_count_value
    row: dict[str, Any] = {
        "group_type": group_type, "group_id": group_id,
        "contact_count": contact_count_value, "degrees_of_freedom": dof if dof else "",
        "epoch_count": int(indices.size),
        "factorization_success_count": int(np.sum(factorization[indices])),
        "chi_square_updates_included": bool(dof > 0),
    }
    for probability, label in ((0.5, "median"), (0.9, "p90"), (0.95, "p95"), (0.99, "p99")):
        row[f"nis_{label}"] = _quantile(values, probability)
    row["nis_mean"] = float(np.mean(values)) if values.size else ""
    row["nis_over_dof_mean"] = float(np.mean(values / dof)) if values.size and dof else ""
    row["nis_over_dof_median"] = float(np.median(values / dof)) if values.size and dof else ""
    if values.size and dof:
        lower, upper = chi2.ppf((0.025, 0.975), dof)
        pvalues = chi2.sf(values, dof)
        row.update({
            "chi_square_lower_95": float(lower), "chi_square_upper_95": float(upper),
            "chi_square_central_95_coverage": float(np.mean((values >= lower) & (values <= upper))),
            "chi_square_pvalue_p01": float(np.quantile(pvalues, 0.01)),
            "chi_square_pvalue_p05": float(np.quantile(pvalues, 0.05)),
            "chi_square_pvalue_median": float(np.median(pvalues)),
            "chi_square_pvalue_p95": float(np.quantile(pvalues, 0.95)),
            "chi_square_pvalue_p99": float(np.quantile(pvalues, 0.99)),
        })
    else:
        row.update({key: "" for key in (
            "chi_square_lower_95", "chi_square_upper_95", "chi_square_central_95_coverage",
            "chi_square_pvalue_p01", "chi_square_pvalue_p05", "chi_square_pvalue_median",
            "chi_square_pvalue_p95", "chi_square_pvalue_p99",
        )})
    return row


def _innovation_summary_row(
    group_type: str, group_id: str, contact_count_value: int,
    indices: np.ndarray, norms: np.ndarray,
) -> dict[str, Any]:
    values = norms[indices]
    return {
        "group_type": group_type, "group_id": group_id,
        "contact_count": contact_count_value,
        "degrees_of_freedom": 3 * contact_count_value if contact_count_value else "",
        "epoch_count": int(indices.size),
        "innovation_norm_p50": _quantile(values, 0.50),
        "innovation_norm_p90": _quantile(values, 0.90),
        "innovation_norm_p95": _quantile(values, 0.95),
        "innovation_norm_p99": _quantile(values, 0.99),
        "innovation_norm_mean": float(np.mean(values)) if values.size else "",
    }


def analyze_nis_and_covariance(
    scratch: Path, cache_path: Path, h5_anchor: Path,
) -> dict[str, Any]:
    windows = _selected_windows(scratch)
    cache = read_cache(cache_path)
    root = scratch / "03_ANALYSIS/10_OBSERVABILITY/04_NIS_AND_COVARIANCE"
    root.mkdir(parents=True, exist_ok=False)
    nis_source = _rows(h5_anchor / "NIS_DIAGNOSTICS.csv")
    if len(nis_source) != STATE_ROWS:
        raise HartleyH6Error("H5 NIS source row count mismatch")
    nis = np.asarray([float(row["nis"]) for row in nis_source])
    factorization = np.asarray([row["factorization_ok"] == "1" for row in nis_source])
    norms = innovation_norms(h5_anchor / "KINEMATIC_INNOVATIONS.csv")
    survivor_mask = np.zeros(STATE_ROWS, dtype=np.uint8)
    survivor_mask[1:] = cache.contact_mask[1:] & ~cache.add_mask[1:]
    survivor_count = np.asarray([int(value).bit_count() for value in survivor_mask])
    emitted_count = np.asarray([int(row["contact_count"]) for row in nis_source])
    if not np.array_equal(survivor_count, emitted_count):
        raise HartleyH6Error("H5 NIS survivor-contact identity mismatch")
    initial_segment = enumerate_segments(cache)[0]
    row_index = np.arange(STATE_ROWS)
    update = survivor_count > 0
    groups: list[tuple[str, str, int, np.ndarray]] = []
    for count in range(1, 5):
        indices = row_index[update & (survivor_count == count)]
        if indices.size:
            groups.append(("CONTACT_COUNT", f"CONTACT_COUNT_{count}", count, indices))
    for mask in sorted(set(map(int, survivor_mask[update]))):
        indices = row_index[update & (survivor_mask == mask)]
        groups.append(("EXACT_CONTACT_SET", contact_set(mask), int(mask).bit_count(), indices))
    initial_four_indices = row_index[
        update & (survivor_count == 4) & (row_index >= initial_segment.start_row)
        & (row_index <= initial_segment.end_row)
    ]
    dynamic_four_indices = row_index[
        update & (survivor_count == 4) & ~(
            (row_index >= initial_segment.start_row) & (row_index <= initial_segment.end_row)
        )
    ]
    if initial_four_indices.size:
        groups.append(("FOUR_CONTACT_PERIOD", "INITIAL_STATIC_FOUR_CONTACT", 4, initial_four_indices))
    if dynamic_four_indices.size:
        groups.append(("FOUR_CONTACT_PERIOD", "DYNAMIC_FOUR_CONTACT", 4, dynamic_four_indices))
    no_update_roles = {
        "INITIALIZATION_NO_CHI_SQUARE": row_index == 0,
        "PROPAGATION_ONLY_FLIGHT": (row_index > 0) & (cache.contact_mask == 0),
        "AUGMENTATION_ONLY_NO_SURVIVOR_UPDATE": (
            (row_index > 0) & (cache.contact_mask != 0) & (survivor_count == 0)
        ),
    }
    for role, mask_values in no_update_roles.items():
        indices = row_index[mask_values]
        if indices.size:
            groups.append(("NO_CHI_SQUARE_UPDATE", role, 0, indices))
    nis_rows = [_nis_summary_row(*group, nis, factorization) for group in groups]
    innovation_rows = [_innovation_summary_row(*group, norms) for group in groups]
    exclusive_csv(root / "TOPOLOGY_CONDITIONED_NIS_SUMMARY.csv", nis_rows, tuple(nis_rows[0]))
    exclusive_csv(
        root / "TOPOLOGY_CONDITIONED_INNOVATION_SUMMARY.csv",
        innovation_rows, tuple(innovation_rows[0]),
    )

    covariance_source = _rows(h5_anchor / "COVARIANCE_DIAGONALS.csv")
    if len(covariance_source) != STATE_ROWS:
        raise HartleyH6Error("H5 covariance-diagonal source row count mismatch")
    gauge_columns = (
        "gauge_yaw_variance", "gauge_translation_x_variance",
        "gauge_translation_y_variance", "gauge_translation_z_variance",
    )
    gauge_timeseries_columns = ("timestamp_ns", "row_index", "topology", "dimension", *gauge_columns)
    exclusive_csv(
        root / "H5_ZERO_RUN_GAUGE_PROJECTION_VARIANCE_TIMESERIES.csv",
        covariance_source, gauge_timeseries_columns,
    )
    covariance_rows: list[dict[str, Any]] = []
    state_diagonal_columns = h5.OUTPUT_SCHEMAS["COVARIANCE_DIAGONALS.csv"][4:31]

    def projected_values(row: Mapping[str, str]) -> tuple[float, float, float]:
        yaw = float(row["gauge_yaw_variance"])
        translation = sum(float(row[column]) for column in gauge_columns[1:])
        total = sum(float(row[column]) for column in state_diagonal_columns if row[column] != "")
        return yaw, translation, total - yaw - translation

    for window in windows:
        start, end = int(window["start_row"]), int(window["end_row"])
        yaw_start, translation_start, observable_start = projected_values(covariance_source[start])
        yaw_end, translation_end, observable_end = projected_values(covariance_source[end])
        covariance_rows.append({
            "evidence_type": "H5_ZERO_CONSTANT_TOPOLOGY_WINDOW",
            "identity": window["window_id"], "run_id": "H5_PRIMARY_0_DEG",
            "contact_set": window["contact_set"], "start_row": start, "end_row": end,
            "yaw_gauge_variance_start": yaw_start, "yaw_gauge_variance_end": yaw_end,
            "yaw_gauge_variance_change": yaw_end - yaw_start,
            "translation_gauge_variance_sum_start": translation_start,
            "translation_gauge_variance_sum_end": translation_end,
            "translation_gauge_variance_sum_change": translation_end - translation_start,
            "observable_subspace_covariance_trace_start": observable_start,
            "observable_subspace_covariance_trace_end": observable_end,
            "observable_subspace_covariance_trace_change": observable_end - observable_start,
            "monotonicity_required": False, "residual": "", "pass": True,
        })
    equivalence_rows = _rows(scratch / "03_ANALYSIS/08_EQUIVALENCE/GAUGE_EQUIVALENCE_SUMMARY.csv")
    for row in equivalence_rows:
        covariance_rows.append({
            "evidence_type": "GAUGE_ENSEMBLE_COVARIANCE_CONGRUENCE",
            "identity": row["run_id"], "run_id": row["run_id"], "contact_set": "ALL",
            "start_row": "", "end_row": "", "yaw_gauge_variance_start": "",
            "yaw_gauge_variance_end": "", "yaw_gauge_variance_change": "",
            "translation_gauge_variance_sum_start": "", "translation_gauge_variance_sum_end": "",
            "translation_gauge_variance_sum_change": "",
            "observable_subspace_covariance_trace_start": "",
            "observable_subspace_covariance_trace_end": "",
            "observable_subspace_covariance_trace_change": "", "monotonicity_required": False,
            "residual": float(row["covariance_congruence_relative_frobenius_difference_max"]),
            "pass": row["pass"] == "true",
        })
    null_summary = json.loads((scratch / "03_ANALYSIS/10_OBSERVABILITY/02_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY.json").read_text())
    for model_key, label in (("ideal", "IDEAL_O_TIMES_G"), ("bias_augmented", "BIAS_AUGMENTED_O_TIMES_G")):
        for row in null_summary[model_key]:
            covariance_rows.append({
                "evidence_type": label, "identity": row["window_id"], "run_id": "H5_PRIMARY_0_DEG",
                "contact_set": "SELECTED_WINDOW", "start_row": "", "end_row": "",
                "yaw_gauge_variance_start": "", "yaw_gauge_variance_end": "",
                "yaw_gauge_variance_change": "", "translation_gauge_variance_sum_start": "",
                "translation_gauge_variance_sum_end": "", "translation_gauge_variance_sum_change": "",
                "observable_subspace_covariance_trace_start": "",
                "observable_subspace_covariance_trace_end": "",
                "observable_subspace_covariance_trace_change": "", "monotonicity_required": False,
                "residual": row["o_times_g_normalized_residual"],
                "pass": row.get("pass", row.get("known_gauge_confirmed", False)),
            })
    for count in range(1, 5):
        measurement = measurement_matrix(count, bias_augmented=True)
        residual = float(np.linalg.norm(measurement @ gauge_basis(count, bias_augmented=True)))
        covariance_rows.append({
            "evidence_type": "CONTACT_H_TIMES_G", "identity": f"CONTACT_COUNT_{count}",
            "run_id": "ANALYTICAL", "contact_set": f"COUNT_{count}", "start_row": "", "end_row": "",
            "yaw_gauge_variance_start": "", "yaw_gauge_variance_end": "",
            "yaw_gauge_variance_change": "", "translation_gauge_variance_sum_start": "",
            "translation_gauge_variance_sum_end": "", "translation_gauge_variance_sum_change": "",
            "observable_subspace_covariance_trace_start": "",
            "observable_subspace_covariance_trace_end": "",
            "observable_subspace_covariance_trace_change": "", "monotonicity_required": False,
            "residual": residual, "pass": residual <= 1.0e-12,
        })
    covariance_columns = tuple(covariance_rows[0])
    exclusive_csv(root / "GAUGE_COVARIANCE_CONSISTENCY.csv", covariance_rows, covariance_columns)
    result = {
        "schema_version": "hartley.h6.nis_covariance.v1",
        "topology_conditioned_nis_group_count": len(nis_rows),
        "zero_contact_post_lifecycle_flight_epoch_count": int(np.sum(no_update_roles["PROPAGATION_ONLY_FLIGHT"])),
        "initialization_no_update_epoch_count": 1,
        "augmentation_only_no_survivor_update_epoch_count": int(np.sum(no_update_roles["AUGMENTATION_ONLY_NO_SURVIVOR_UPDATE"])),
        "raw_nis_pooled_across_contact_counts": False,
        "sigma_fk_tuned": False,
        "low_nis_interpretation": "CONSERVATIVE_AND_OR_CORRELATED_PROXY_STATISTICS_NOT_ACCURACY",
        "reference_open_count": 0, "trace_open_count": 0,
    }
    exclusive_json(root / "NIS_AND_COVARIANCE_FREEZE.json", result)
    return result


def _runtime_summary(scratch: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for run_id, yaw, _ in YAW_MEMBERS:
        rows = _rows(scratch / "02_FROZEN_RUNS" / run_id / "RUNTIME.csv")
        if len(rows) != 1 or rows[0]["threads_verified"] != "true":
            raise HartleyH6Error("member runtime/thread evidence mismatch")
        output.append({
            "run_id": run_id, "initial_yaw_deg": yaw,
            "state_rows": int(rows[0]["state_rows"]),
            "propagation_calls": int(rows[0]["propagation_calls"]),
            "eq61_calls": int(rows[0]["eq61_calls"]),
            "eq52_calls": int(rows[0]["eq52_calls"]),
            "threads_verified": True, "elapsed_seconds": float(rows[0]["elapsed_seconds"]),
        })
    return output


BLOCKED_TERMINAL = "BLOCKED_LSE01_H6_GAUGE_EQUIVARIANCE_FAILURE"
NOT_EVALUATED_AFTER_GAUGE_BLOCKER = "NOT_EVALUATED_DUE_TO_PRIOR_GAUGE_EQUIVARIANCE_BLOCKER"
FORBIDDEN_ACCESS_COUNT_FIELDS = (
    "reference_open_count", "trace_open_count", "GNSS_input_count",
    "Go2_onboard_pose_or_yaw_input_count", "LegSA_output_input_count",
    "EXT_output_input_count",
)


def _require_file_identity(path: Path, identity: Mapping[str, Any], label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise HartleyH6Error(f"missing or unsafe blocked-closure file: {label}")
    if path.stat().st_size != int(identity["size"]) or sha256_file(path) != identity["sha256"]:
        raise HartleyH6Error(f"blocked-closure file identity mismatch: {label}")


def _validate_blocked_prerequisites(
    scratch: Path, repository: Path, h5_anchor: Path,
) -> dict[str, Any]:
    parity_path = scratch / "00_ADMIN/H6_ZERO_DEGREE_RUNNER_PARITY.json"
    parity = json.loads(parity_path.read_text())
    if not parity.get("parity_pass") or parity.get("zero_degree_replay_count") != 1:
        raise HartleyH6Error("blocked closure requires passed one-time zero-degree parity")
    if parity.get("state_row_count_anchor") != STATE_ROWS or parity.get("state_row_count_replay") != STATE_ROWS:
        raise HartleyH6Error("blocked closure zero-degree parity row identity mismatch")
    if any(parity.get(key, 0) != 0 for key in ("reference_open_count", "trace_open_count")):
        raise HartleyH6Error("blocked closure zero-degree parity has forbidden access")
    if Path(parity.get("h5_local_anchor", "")) != h5_anchor:
        raise HartleyH6Error("blocked closure H5 primary anchor identity mismatch")

    tolerance_path = scratch / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml"
    tolerance_freeze_path = scratch / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY_FREEZE.json"
    tolerance_freeze = json.loads(tolerance_freeze_path.read_text())
    if (
        tolerance_freeze.get("nonzero_yaw_run_count_at_freeze") != 0
        or tolerance_freeze.get("sha256") != sha256_file(tolerance_path)
        or tolerance_freeze.get("reference_open_count") != 0
        or tolerance_freeze.get("trace_open_count") != 0
    ):
        raise HartleyH6Error("blocked closure tolerance preregistration identity mismatch")

    member_identities: dict[str, Any] = {}
    native_source_manifests: set[str] = set()
    executable_hashes: set[str] = set()
    for run_id, yaw, _ in YAW_MEMBERS:
        member = scratch / "02_FROZEN_RUNS" / run_id
        freeze_path = member / "NATIVE_FREEZE.json"
        freeze = json.loads(freeze_path.read_text())
        if (
            freeze.get("run_id") != run_id
            or float(freeze.get("initial_gauge_yaw_deg")) != yaw
            or freeze.get("state_rows") != STATE_ROWS
            or set(freeze.get("files", {})) != set(COMPACT_RUN_FILES)
            or freeze.get("reference_open_count") != 0
            or freeze.get("trace_open_count") != 0
        ):
            raise HartleyH6Error(f"blocked closure compact native freeze mismatch: {run_id}")
        for name, identity in freeze["files"].items():
            _require_file_identity(member / name, identity, f"{run_id}/{name}")
        summary = json.loads((member / "NATIVE_SUMMARY.json").read_text())
        if (
            summary.get("run_id") != run_id
            or summary.get("state_rows") != STATE_ROWS
            or summary.get("gauge_equivalence_pass") is not False
            or summary.get("contact_identity_set_and_dimension_match_every_epoch") is not True
            or any(summary.get(key) != 0 for key in FORBIDDEN_ACCESS_COUNT_FIELDS)
        ):
            raise HartleyH6Error(f"blocked closure native summary mismatch: {run_id}")
        native_source_manifests.add(summary["scoped_source_manifest_sha256"])
        executable_hashes.add(summary["native_executable_sha256"])
        member_identities[run_id] = {
            "initial_yaw_deg": yaw,
            "native_freeze_sha256": sha256_file(freeze_path),
            "native_scoped_source_manifest_sha256": summary["scoped_source_manifest_sha256"],
            "native_executable_sha256": summary["native_executable_sha256"],
        }
    if len(native_source_manifests) != 1 or len(executable_hashes) != 1:
        raise HartleyH6Error("blocked closure native worker identity is not deterministic")

    equivalence_root = scratch / "03_ANALYSIS/08_EQUIVALENCE"
    equivalence_path = equivalence_root / "GAUGE_EQUIVALENCE_FREEZE.json"
    equivalence = json.loads(equivalence_path.read_text())
    required_equivalence_files = {
        "GAUGE_EQUIVALENCE_EPOCH_METRICS.csv",
        "GAUGE_EQUIVALENCE_CHECKPOINT_METRICS.csv",
        "GAUGE_EQUIVALENCE_SUMMARY.csv",
        "GAUGE_NATIVE_YAW_OFFSET_SUMMARY.csv",
    }
    if (
        equivalence.get("gauge_equivalence_pass") is not False
        or equivalence.get("nonzero_yaw_run_count") != 6
        or equivalence.get("state_rows_per_run") != STATE_ROWS
        or set(equivalence.get("files", {})) != required_equivalence_files
        or equivalence.get("reference_open_count") != 0
        or equivalence.get("trace_open_count") != 0
    ):
        raise HartleyH6Error("blocked closure equivalence failure freeze mismatch")
    for name, identity in equivalence["files"].items():
        _require_file_identity(equivalence_root / name, identity, name)
    equivalence_rows = _rows(equivalence_root / "GAUGE_EQUIVALENCE_SUMMARY.csv")
    if {row["run_id"] for row in equivalence_rows} != set(YAW_BY_RUN_ID) or len(equivalence_rows) != 6:
        raise HartleyH6Error("blocked closure equivalence summary member identity mismatch")
    contact_failures: list[dict[str, Any]] = []
    for row in equivalence_rows:
        if row["pass"] != "false":
            raise HartleyH6Error("blocked closure requires a failed member summary")
        contact_max = float(row["maximum_matched_contact_position_difference_m_max"])
        contact_tolerance = float(row["maximum_matched_contact_position_difference_m_tolerance"])
        if contact_max <= contact_tolerance:
            raise HartleyH6Error("blocked closure contact metric did not exceed its frozen tolerance")
        for metric in (
            "orientation_geodesic_difference_rad", "velocity_difference_m_per_s",
            "position_difference_m", "gyro_bias_difference_rad_per_s",
            "accelerometer_bias_difference_m_per_s2", "relative_yaw_increment_difference_rad",
            "innovation_norm_difference", "native_yaw_offset_residual_rad",
            "covariance_congruence_relative_frobenius_difference",
        ):
            if float(row[f"{metric}_max"]) > float(row[f"{metric}_tolerance"]):
                raise HartleyH6Error(f"blocked closure has an unexpected additional failed metric: {metric}")
        contact_failures.append({
            "run_id": row["run_id"],
            "initial_yaw_deg": float(row["initial_yaw_deg"]),
            "maximum_matched_contact_position_difference_m": contact_max,
            "frozen_tolerance_m": contact_tolerance,
        })
    yaw_rows = _rows(equivalence_root / "GAUGE_NATIVE_YAW_OFFSET_SUMMARY.csv")
    if len(yaw_rows) != 6 or any(row["pass"] != "true" for row in yaw_rows):
        raise HartleyH6Error("blocked closure native yaw separation evidence mismatch")

    observability_root = scratch / "03_ANALYSIS/10_OBSERVABILITY"
    inventory_path = observability_root / "00_SEGMENT_INVENTORY/OBSERVABILITY_SEGMENT_INVENTORY.csv"
    zero_segments_path = observability_root / "00_SEGMENT_INVENTORY/ZERO_CONTACT_PROPAGATION_ONLY_SEGMENTS.csv"
    selection_path = observability_root / "01_WINDOW_SELECTION/H6_OBSERVABILITY_WINDOW_SELECTION.csv"
    selection_freeze_path = observability_root / "01_WINDOW_SELECTION/H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json"
    selection = json.loads(selection_freeze_path.read_text())
    if (
        selection.get("svd_call_count_before_freeze") != 0
        or selection.get("rank_output_read_count_before_freeze") != 0
        or selection.get("selection_forbidden_input_count") != 0
        or selection.get("segment_inventory_sha256") != sha256_file(inventory_path)
        or selection.get("selection_csv_sha256") != sha256_file(selection_path)
        or selection.get("reference_open_count") != 0
        or selection.get("trace_open_count") != 0
    ):
        raise HartleyH6Error("blocked closure observability window selection freeze mismatch")
    if not zero_segments_path.is_file():
        raise HartleyH6Error("blocked closure zero-contact segment inventory is missing")
    forbidden_analysis_directories = (
        observability_root / "02_IDEAL_BIAS_FREE",
        observability_root / "03_BIAS_AUGMENTED",
        observability_root / "04_NIS_AND_COVARIANCE",
    )
    if any(path.exists() for path in forbidden_analysis_directories):
        raise HartleyH6Error("blocked closure found analysis that should be not evaluated")

    contract_path = repository / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_H6_EXECUTION_CONTRACT.yaml"
    if not contract_path.is_file():
        raise HartleyH6Error("blocked closure execution contract is missing")
    return {
        "parity": parity,
        "parity_sha256": sha256_file(parity_path),
        "tolerance_freeze": tolerance_freeze,
        "tolerance_registry_sha256": sha256_file(tolerance_path),
        "member_identities": member_identities,
        "native_scoped_source_manifest_sha256": next(iter(native_source_manifests)),
        "native_executable_sha256": next(iter(executable_hashes)),
        "equivalence": equivalence,
        "equivalence_freeze_sha256": sha256_file(equivalence_path),
        "contact_failures": sorted(contact_failures, key=lambda row: row["initial_yaw_deg"]),
        "native_yaw_separation_max_residual_rad": max(
            float(row["native_yaw_offset_residual_max_rad"]) for row in yaw_rows
        ),
        "selection": selection,
        "segment_count": len(_rows(inventory_path)),
        "zero_contact_segment_count": len(_rows(zero_segments_path)),
        "selected_windows": _rows(selection_path),
        "contract_path": contract_path,
        "contract_sha256": sha256_file(contract_path),
        "runtime": _runtime_summary(scratch),
    }


def finalize_blocked_h6(scratch: Path, repository: Path, h5_anchor: Path) -> dict[str, Any]:
    evidence = _validate_blocked_prerequisites(scratch, repository, h5_anchor)
    report_root = scratch / "03_ANALYSIS/11_REPORT"
    report_root.mkdir(parents=True, exist_ok=False)
    cleanup = json.loads((scratch / "00_ADMIN/H5_SCRATCH_CLEANUP_LEDGER.json").read_text())
    health = json.loads((scratch / "00_ADMIN/H6_STORAGE_HEALTH_READ_ONLY.json").read_text())
    tests_path = scratch / "00_ADMIN/H6_TEST_RESULTS.json"
    tests = json.loads(tests_path.read_text()) if tests_path.is_file() else {"status": "PENDING_FINAL_TEST_EXECUTION"}
    blocked_source_paths = (
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6.py",
        "scripts/paper_rebuild/run_hartley_h6.py",
        "tests/paper_rebuild/test_hartley_h6_contracts.py",
        "tests/paper_rebuild/test_hartley_h6_backend.py",
    )
    blocked_source_files = {
        relative: {"size": (repository / relative).stat().st_size, "sha256": sha256_file(repository / relative)}
        for relative in blocked_source_paths
    }
    blocked_source_digest = hashlib.sha256(
        json.dumps(blocked_source_files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    not_evaluated = NOT_EVALUATED_AFTER_GAUGE_BLOCKER
    status = {
        "schema_version": "hartley.h6.status.v1",
        "terminal_status": BLOCKED_TERMINAL,
        "task_start_head": TASK_START_HEAD,
        "method_id": METHOD_ID, "backend_id": BACKEND_ID,
        "data_mode": "real_by2_raw", "h5_primary_anchor_reused": True,
        "nonzero_yaw_run_count": 6, "zero_degree_replay_count": 1,
        "zero_degree_replay_payload_retained": False,
        "six_nonzero_native_runs_completed": True,
        "six_compact_native_freezes_validated": True,
        "gauge_equivalence_pass": False,
        "gauge_equivalence_failure_metric": "maximum_matched_contact_position_difference_m",
        "contact_position_failures": evidence["contact_failures"],
        "inverse_gauge_non_contact_metrics_pass": True,
        "covariance_congruence_pass": True,
        "native_yaw_separation_pass": True,
        "native_yaw_separation_max_residual_rad": evidence["native_yaw_separation_max_residual_rad"],
        "ideal_observability_status": not_evaluated,
        "ideal_observability_gauge_dimension": not_evaluated,
        "bias_augmented_observability_status": not_evaluated,
        "bias_augmented_known_gauge_confirmed": False,
        "topology_conditioned_nis_status": not_evaluated,
        "gauge_covariance_full_consistency_status": not_evaluated,
        "observability_svd_call_count": 0,
        "observability_rank_output_read_count": 0,
        "reference_open_count": 0, "trace_open_count": 0,
        "GNSS_input_count": 0, "Go2_onboard_pose_or_yaw_input_count": 0,
        "LegSA_output_input_count": 0, "EXT_output_input_count": 0,
        "absolute_yaw_RMSE_computed": False,
        "absolute_position_RMSE_computed": False,
        "relative_pose_error_versus_trace_computed": False,
        "h7_authorized": False, "h7_executed": False,
        "ext06_executed": False, "horizontal18_executed": False,
        "canonical541_executed": False,
        "raw_sha256": RAW_SHA256, "complete_prefix_sha256": PREFIX_SHA256,
        "provider_cache_sha256": CACHE_SHA256,
        "contact_event_input_ledger_sha256": EVENT_LEDGER_SHA256,
        "state_rows_per_member": STATE_ROWS,
        "native_executable_sha256": evidence["native_executable_sha256"],
        "native_scoped_source_manifest_sha256": evidence["native_scoped_source_manifest_sha256"],
        "blocked_closure_source_manifest_sha256": blocked_source_digest,
        "runner_parity": evidence["parity"],
        "runner_parity_sha256": evidence["parity_sha256"],
        "tolerance_registry_sha256": evidence["tolerance_registry_sha256"],
        "gauge_equivalence_freeze_sha256": evidence["equivalence_freeze_sha256"],
        "observability_segment_count": evidence["segment_count"],
        "observability_zero_contact_segment_count": evidence["zero_contact_segment_count"],
        "observability_selected_window_count": evidence["selection"]["selected_window_count_after_role_deduplication"],
        "observability_window_selection_frozen_before_svd": True,
        "storage_health": health,
        "h5_scratch_cleanup": {
            "deleted_root_count": cleanup["deleted_root_count"],
            "bytes_reclaimed": cleanup["bytes_reclaimed"],
            "accepted_v3_disposition": cleanup["accepted_v3_disposition"],
        },
        "runtime": evidence["runtime"], "tests": tests,
        "serialization_diagnostic": {
            "interpretation": "EXPLAINS_OBSERVED_CONTACT_CSV_FLOOR_BUT_DOES_NOT_EXEMPT_FROZEN_TOLERANCE_FAILURE",
            "h5_contact_state_stream_precision": "DEFAULT_CPP_STREAM_PRECISION_6_SIGNIFICANT_DIGITS",
            "representative_world_coordinate_scale_m": 100.0,
            "representative_decimal_step_m": 0.001,
        },
        "external_stage_published": False,
        "scratch_retained_due_to_unhealthy_g": True,
    }
    status_path = report_root / "LSE01_H6_STATUS.json"
    exclusive_json(status_path, status)
    run_lines = "\n".join(
        f"- `{row['run_id']}` ({row['initial_yaw_deg']:+.0f} deg): "
        f"{row['elapsed_seconds']:.6f} s, 63,277 rows, threads verified"
        for row in evidence["runtime"]
    )
    failure_lines = "\n".join(
        f"- `{row['run_id']}`: {row['maximum_matched_contact_position_difference_m']:.17g} m "
        f"> frozen {row['frozen_tolerance_m']:.17g} m"
        for row in evidence["contact_failures"]
    )
    window_lines = "\n".join(
        f"- `{row['window_id']}`: rows {row['start_row']}-{row['end_row']}, "
        f"contacts `{row['contact_set']}`, roles `{row['selection_roles']}`"
        for row in evidence["selected_windows"]
    )
    report = f"""# LSE01 H6 Gauge and Observability Report

Status: `{BLOCKED_TERMINAL}`.

The frozen H5 0-degree primary anchor was reused. The one temporary 0-degree replay passed exact scientific parity across 63,277 rows, contact/event streams, NIS/innovation streams, final state, and canonical covariance checkpoint arrays; its payload was then deleted. Six nonzero-yaw chronological native sequences completed with one numerical-library thread per process.

## Native run identities and deterministic execution

{run_lines}

The preregistered sign is `Q_alpha=Exp((g/||g||) alpha)` about `g/||g||=[0,0,-1]`, applied on the left, so conventional positive-Z Euler yaw offsets are `-alpha`. Native yaw separation passed with maximum wrapped residual {evidence['native_yaw_separation_max_residual_rad']:.17g} rad. Contact event identity, state dimension, orientation, velocity, position, both bias vectors, relative yaw increments, innovation norms, and covariance congruence all passed their frozen tolerances.

## Exact blocker

Only the maximum matched-contact-position metric exceeded its immutable preregistered `0.0005 m` tolerance:

{failure_lines}

This triggers `{BLOCKED_TERMINAL}` exactly. A serialization diagnostic explains the scale but does not waive or redefine the preregistered gate: the frozen H5 `CONTACT_STATE.csv` was written with the C++ stream default of six significant digits, and the failing interval has world coordinates around 100 m, where the decimal output step is about 0.001 m. No tolerance, metric, filter state, or scientific output was changed after observing the result.

## Window inventory frozen before SVD

The selection inventory contains {evidence['segment_count']} maximal constant-contact segments, including {evidence['zero_contact_segment_count']} separately reported zero-contact propagation-only segments. Selection used only timestamps, contact masks, gyro, and accelerometer and froze with `svd_call_count_before_freeze=0` and `rank_output_read_count_before_freeze=0`.

{window_lines}

Ideal bias-free observability, bias-augmented observability, topology-conditioned NIS/innovation, and full gauge-covariance consistency are `{not_evaluated}`. No real observability SVD or NIS analysis was run after the prior gauge-equivalence blocker.

## Storage, cleanup, and boundaries

G remained `Warning / Full Repair Needed`; no repair command was invoked. H5 V1/V2 were deleted only after compact uniqueness/duplicate proof, reclaiming {cleanup['bytes_reclaimed']} bytes; accepted V3 and the H6 scratch remain retained. All evidence counters are zero for reference, trace, GNSS, Go2 onboard pose/yaw, LegSA output, and EXT output. Absolute yaw RMSE, absolute position RMSE, and trace-relative pose error were not computed. H7 is not authorized and remains unexecuted.
"""
    report_path = report_root / "LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md"
    exclusive_write(report_path, report.encode())

    excluded_roots = {"00_BUILD", "01_NATIVE_RAW", "04_PUBLICATION"}
    freeze_candidates = [
        path for path in scratch.rglob("*")
        if path.is_file()
        and path.relative_to(scratch).parts[0] not in excluded_roots
        and "__pycache__" not in path.parts
        and path.name != "H6_MASTER_FREEZE.json"
    ]
    master = {
        "schema_version": "hartley.h6.master_freeze.v1",
        "terminal_status": BLOCKED_TERMINAL,
        "scientific_scope": "BLOCKED_CLOSURE_NO_REAL_OBSERVABILITY_SVD_OR_NIS_ANALYSIS",
        "tracked_execution_contract": {
            "path": evidence["contract_path"].relative_to(repository).as_posix(),
            "sha256": evidence["contract_sha256"],
        },
        "tracked_blocked_closure_sources": blocked_source_files,
        "tracked_blocked_closure_source_manifest_sha256": blocked_source_digest,
        "files": {
            path.relative_to(scratch).as_posix(): {
                "size": path.stat().st_size, "sha256": sha256_file(path),
            }
            for path in sorted(freeze_candidates)
        },
        "reference_open_count": 0, "trace_open_count": 0,
        "GNSS_input_count": 0, "Go2_onboard_pose_or_yaw_input_count": 0,
        "LegSA_output_input_count": 0, "EXT_output_input_count": 0,
        "observability_svd_call_count": 0,
        "h7_executed": False,
    }
    exclusive_json(scratch / "H6_MASTER_FREEZE.json", master)
    return status


def finalize_h6(scratch: Path, h5_anchor: Path) -> dict[str, Any]:
    report_root = scratch / "03_ANALYSIS" / "11_REPORT"
    report_root.mkdir(parents=True, exist_ok=False)
    parity = json.loads((scratch / "00_ADMIN/H6_ZERO_DEGREE_RUNNER_PARITY.json").read_text())
    equivalence = json.loads((scratch / "03_ANALYSIS/08_EQUIVALENCE/GAUGE_EQUIVALENCE_FREEZE.json").read_text())
    selection = json.loads((scratch / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION/H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json").read_text())
    observability = json.loads((scratch / "03_ANALYSIS/10_OBSERVABILITY/03_BIAS_AUGMENTED/OBSERVABILITY_ANALYSIS_FREEZE.json").read_text())
    nis = json.loads((scratch / "03_ANALYSIS/10_OBSERVABILITY/04_NIS_AND_COVARIANCE/NIS_AND_COVARIANCE_FREEZE.json").read_text())
    cleanup = json.loads((scratch / "00_ADMIN/H5_SCRATCH_CLEANUP_LEDGER.json").read_text())
    health = json.loads((scratch / "00_ADMIN/H6_STORAGE_HEALTH_READ_ONLY.json").read_text())
    tests_path = scratch / "00_ADMIN/H6_TEST_RESULTS.json"
    tests = json.loads(tests_path.read_text()) if tests_path.is_file() else {"status": "PENDING_FINAL_TEST_EXECUTION"}
    equivalence_rows = _rows(scratch / "03_ANALYSIS/08_EQUIVALENCE/GAUGE_EQUIVALENCE_SUMMARY.csv")
    yaw_rows = _rows(scratch / "03_ANALYSIS/08_EQUIVALENCE/GAUGE_NATIVE_YAW_OFFSET_SUMMARY.csv")
    nullspace = json.loads((scratch / "03_ANALYSIS/10_OBSERVABILITY/02_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY.json").read_text())
    nis_rows = _rows(scratch / "03_ANALYSIS/10_OBSERVABILITY/04_NIS_AND_COVARIANCE/TOPOLOGY_CONDITIONED_NIS_SUMMARY.csv")
    runtime = _runtime_summary(scratch)
    all_required = (
        parity.get("parity_pass") is True
        and equivalence.get("gauge_equivalence_pass") is True
        and observability.get("ideal_rank_nullity_pass") is True
        and observability.get("bias_augmented_known_gauge_confirmed") is True
        and len(runtime) == 6
    )
    if not all_required:
        raise HartleyH6Error("H6 finalization prerequisites did not pass")
    status = {
        "schema_version": "hartley.h6.status.v1",
        "terminal_status": "PASS_LSE01_H6_REAL_DATA_GAUGE_AND_OBSERVABILITY_CONFIRMED",
        "task_start_head": TASK_START_HEAD,
        "method_id": METHOD_ID, "backend_id": BACKEND_ID,
        "data_mode": "real_by2_raw", "h5_primary_anchor_reused": True,
        "nonzero_yaw_run_count": 6, "zero_degree_replay_count": 1,
        "zero_degree_replay_payload_retained": False,
        "gauge_equivalence_pass": True,
        "ideal_observability_gauge_dimension": 4,
        "bias_augmented_known_gauge_confirmed": True,
        "reference_open_count": 0, "trace_open_count": 0,
        "GNSS_input_count": 0, "Go2_onboard_pose_or_yaw_input_count": 0,
        "LegSA_output_input_count": 0, "EXT_output_input_count": 0,
        "absolute_yaw_RMSE_computed": False,
        "absolute_position_RMSE_computed": False,
        "relative_pose_error_versus_trace_computed": False,
        "h7_authorized": True, "h7_executed": False,
        "ext06_executed": False, "horizontal18_executed": False,
        "canonical541_executed": False,
        "raw_sha256": RAW_SHA256, "complete_prefix_sha256": PREFIX_SHA256,
        "provider_cache_sha256": CACHE_SHA256,
        "contact_event_input_ledger_sha256": EVENT_LEDGER_SHA256,
        "state_rows_per_member": STATE_ROWS,
        "storage_health": health,
        "h5_scratch_cleanup": {
            "deleted_root_count": cleanup["deleted_root_count"],
            "bytes_reclaimed": cleanup["bytes_reclaimed"],
            "accepted_v3_disposition": cleanup["accepted_v3_disposition"],
        },
        "runner_parity": parity,
        "gauge_equivalence_freeze_sha256": sha256_file(scratch / "03_ANALYSIS/08_EQUIVALENCE/GAUGE_EQUIVALENCE_FREEZE.json"),
        "observability_window_count": selection["selected_window_count_after_role_deduplication"],
        "observability": observability,
        "nis_and_covariance": nis,
        "runtime": runtime, "tests": tests,
        "external_stage_published": False,
        "scratch_retained_due_to_unhealthy_g": True,
    }
    status_path = report_root / "LSE01_H6_STATUS.json"
    exclusive_json(status_path, status)
    ideal_lines = "; ".join(
        f"{row['window_id']}: rank {row['expected_rank']}, nullity 4, contacts {row['contact_count']}"
        for row in nullspace["ideal"]
    )
    bias_extra = "; ".join(
        f"{row['window_id']}: nullity {row['raw_nullity']} (additional {row['additional_numerical_nullity']}), {row['excitation_label']}"
        for row in nullspace["bias_augmented"]
    )
    maximum_metrics = {
        key: max(float(row[key]) for row in equivalence_rows)
        for key in equivalence_rows[0]
        if key.endswith("_max")
    }
    yaw_max = max(float(row["native_yaw_offset_residual_max_rad"]) for row in yaw_rows)
    nis_count_lines = "; ".join(
        f"{row['group_id']}: n={row['epoch_count']}, mean={row['nis_mean'] or 'NA'}"
        for row in nis_rows if row["group_type"] == "CONTACT_COUNT"
    )
    report = f"""# LSE01 H6 Gauge and Observability Report

Status: `PASS_LSE01_H6_REAL_DATA_GAUGE_AND_OBSERVABILITY_CONFIRMED`.

H6 reused the frozen H5 0-degree primary anchor and executed exactly six nonzero-yaw chronological native sequences on the immutable 63,277-row BY2 proprioceptive cache. The one temporary 0-degree replay passed exact scientific parity and its payload was deleted after the parity report was frozen.

## Gauge ensemble

The preregistered gauge uses `Q_alpha=Exp((g/||g||) alpha)` with `g/||g||=[0,0,-1]` and left multiplication. Conventional positive-Z Euler yaw offsets are therefore `-alpha`; no result selected this sign. All six inverse-gauge sequences passed every frozen epochwise and checkpoint tolerance. Maximum metrics: `{json.dumps(maximum_metrics, sort_keys=True)}`. Maximum native-yaw offset residual: `{yaw_max:.17g}` rad.

## Observability

Window selection used only provider timestamps, frozen contact identity sets, and IMU excitation and froze with `svd_call_count_before_freeze=0`. It selected {selection['selected_window_count_after_role_deduplication']} deduplicated eligible windows. Ideal results: {ideal_lines}. Every eligible ideal window retained the four-dimensional gauge (three translations plus one gravity-axis rotation) at 0.1x/1x/10x rank thresholds.

The bias-augmented real-trajectory model used the H5 state ordering, actual corrected IMU, actual timestamps, backend analytical Phi equations, and the same contact H. Known-gauge residuals/principal angles passed. Extra short-window numerical nullity was recorded as weak or insufficiently excited, never relabelled as gauge: {bias_extra}.

## NIS, innovation, and covariance

NIS was conditioned on survivor-corrected contact set with DoF `3*count`; zero-contact, initialization, and augmentation-only rows were excluded from chi-square update claims and reported separately. Contact-count summaries: {nis_count_lines}. Low NIS is interpreted only as conservative and/or correlated FK-proxy statistics, not high accuracy; `sigma_fk=0.010 m` was not tuned.

Covariance consistency is supported by ensemble congruence, ideal and bias-augmented `O*G`, and contact `H*G`. H5 gauge-projection variances were retained as a time series and constant-topology changes were reported without a monotonicity claim.

## Boundaries

All native and structural artifacts were frozen with `reference_open_count=0`, `trace_open_count=0`, `GNSS_input_count=0`, `Go2_onboard_pose_or_yaw_input_count=0`, `LegSA_output_input_count=0`, and `EXT_output_input_count=0`. No absolute yaw/position RMSE or trace-relative pose error was computed. H7 remains unexecuted.
"""
    exclusive_write(report_root / "LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md", report.encode())
    exclusive_json(
        scratch / "03_ANALYSIS/08_EQUIVALENCE/H5_PRIMARY_0_DEG_REFERENCE_POINTER.json",
        {
            "schema_version": "hartley.h6.h5_reference_pointer.v1",
            "h5_primary_anchor_reused": True,
            "path": "../../08_BY2_NATIVE/01_PRIMARY_GO2_ALLAN_EQ61_FK10MM",
            "native_freeze_sha256": sha256_file(h5_anchor / "NATIVE_FREEZE.json"),
            "nav_sha256": sha256_file(h5_anchor / "NAV.csv"),
            "reference_open_count": 0, "trace_open_count": 0,
        },
    )
    excluded_roots = {"00_BUILD", "01_NATIVE_RAW", "04_PUBLICATION"}
    freeze_candidates = [
        path for path in scratch.rglob("*")
        if path.is_file()
        and path.relative_to(scratch).parts[0] not in excluded_roots
        and "__pycache__" not in path.parts
        and path.name != "H6_MASTER_FREEZE.json"
    ]
    master = {
        "schema_version": "hartley.h6.master_freeze.v1",
        "terminal_status": status["terminal_status"],
        "files": {
            path.relative_to(scratch).as_posix(): {"size": path.stat().st_size, "sha256": sha256_file(path)}
            for path in sorted(freeze_candidates)
        },
        "reference_open_count": 0, "trace_open_count": 0,
        "GNSS_input_count": 0, "Go2_onboard_pose_or_yaw_input_count": 0,
        "LegSA_output_input_count": 0, "EXT_output_input_count": 0,
    }
    exclusive_json(scratch / "H6_MASTER_FREEZE.json", master)
    return status


def _publication_sources(scratch: Path, repository: Path) -> dict[str, Path]:
    sources: dict[str, Path] = {
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml": scratch / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY_FREEZE.json": scratch / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY_FREEZE.json",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/HARTLEY_H6_EXECUTION_CONTRACT.yaml": repository / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_H6_EXECUTION_CONTRACT.yaml",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_ZERO_DEGREE_RUNNER_PARITY.json": scratch / "00_ADMIN/H6_ZERO_DEGREE_RUNNER_PARITY.json",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H5_SCRATCH_CLEANUP_LEDGER.json": scratch / "00_ADMIN/H5_SCRATCH_CLEANUP_LEDGER.json",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_STORAGE_HEALTH_READ_ONLY.json": scratch / "00_ADMIN/H6_STORAGE_HEALTH_READ_ONLY.json",
    }
    for run_id, _, destination in YAW_MEMBERS:
        for name in (*COMPACT_RUN_FILES, "NATIVE_FREEZE.json"):
            sources[f"09_GAUGE_ENSEMBLE/{destination}/{name}"] = scratch / "02_FROZEN_RUNS" / run_id / name
    equivalence = scratch / "03_ANALYSIS/08_EQUIVALENCE"
    for path in equivalence.iterdir():
        if path.is_file():
            sources[f"09_GAUGE_ENSEMBLE/08_EQUIVALENCE/{path.name}"] = path
    observability = scratch / "03_ANALYSIS/10_OBSERVABILITY"
    for relative_directory in (
        "00_SEGMENT_INVENTORY", "01_WINDOW_SELECTION", "02_IDEAL_BIAS_FREE",
        "03_BIAS_AUGMENTED", "04_NIS_AND_COVARIANCE",
    ):
        for path in (observability / relative_directory).iterdir():
            if path.is_file():
                sources[f"10_OBSERVABILITY/{relative_directory}/{path.name}"] = path
    report = scratch / "03_ANALYSIS/11_REPORT"
    sources["11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md"] = report / "LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md"
    return sources


def publish_h6(scratch: Path, repository: Path, stage_root: Path, h5_anchor: Path) -> dict[str, Any]:
    status_path = scratch / "03_ANALYSIS/11_REPORT/LSE01_H6_STATUS.json"
    status = json.loads(status_path.read_text())
    master_path = scratch / "H6_MASTER_FREEZE.json"
    master = json.loads(master_path.read_text())
    if status.get("terminal_status") != "PASS_LSE01_H6_REAL_DATA_GAUGE_AND_OBSERVABILITY_CONFIRMED":
        raise HartleyH6Error("publication requires passed H6 status")
    if any(status.get(key) != 0 for key in (
        "reference_open_count", "trace_open_count", "GNSS_input_count",
        "Go2_onboard_pose_or_yaw_input_count", "LegSA_output_input_count", "EXT_output_input_count",
    )):
        raise HartleyH6Error("publication forbidden-access counters are nonzero")
    if not stage_root.is_dir() or stage_root.is_symlink():
        raise HartleyH6Error("existing LSE01 external stage root is missing/unsafe")
    if (stage_root / "09_GAUGE_ENSEMBLE").exists() or (stage_root / "10_OBSERVABILITY").exists():
        raise HartleyH6Error("H6 external destination already exists")
    sources = _publication_sources(scratch, repository)
    pointer_scratch = scratch / "03_ANALYSIS/08_EQUIVALENCE/H5_PRIMARY_0_DEG_REFERENCE_POINTER.json"
    sources["09_GAUGE_ENSEMBLE/04_YAW_000_REFERENCE_TO_H5/H5_PRIMARY_0_DEG_REFERENCE_POINTER.json"] = pointer_scratch
    source_manifest = {
        relative: {"size": source.stat().st_size, "sha256": sha256_file(source)}
        for relative, source in sorted(sources.items())
    }
    manifest = {
        "schema_version": "hartley.h6.external_publication_manifest.v1",
        "master_freeze_sha256": sha256_file(master_path),
        "source_file_count": len(sources), "files": source_manifest,
        "publication_mode": "EXCLUSIVE_CREATE_GUARDED_HASH_PARITY",
        "g_health": "WARNING_FULL_REPAIR_NEEDED",
        "accepted_scratch_retained": True,
    }
    publication_root = scratch / "04_PUBLICATION"
    publication_root.mkdir(exist_ok=False)
    manifest_path = publication_root / "H6_EXTERNAL_PUBLICATION_MANIFEST.json"
    exclusive_json(manifest_path, manifest)
    for relative, source in sorted(sources.items()):
        destination = stage_root / relative
        if destination.exists() or destination.is_symlink():
            raise HartleyH6Error(f"external H6 destination collision: {destination}")
        copy_exclusive(source, destination)
    parity_files: dict[str, Any] = {}
    for relative, identity in source_manifest.items():
        destination = stage_root / relative
        actual = {"size": destination.stat().st_size, "sha256": sha256_file(destination)}
        parity_files[relative] = {**actual, "equal": actual == identity}
    status["external_stage_published"] = True
    status["external_stage_path"] = str(stage_root)
    status["external_publication_file_count"] = len(parity_files) + 3
    status["external_publication_all_bytes_equal"] = all(row["equal"] for row in parity_files.values())
    post_status = publication_root / "LSE01_H6_STATUS.json"
    exclusive_json(post_status, status)
    copy_exclusive(post_status, stage_root / "11_REPORT/LSE01_H6_STATUS.json")
    status_identity = {"size": post_status.stat().st_size, "sha256": sha256_file(post_status)}
    external_status = stage_root / "11_REPORT/LSE01_H6_STATUS.json"
    parity_files["11_REPORT/LSE01_H6_STATUS.json"] = {
        **status_identity,
        "equal": external_status.stat().st_size == status_identity["size"]
        and sha256_file(external_status) == status_identity["sha256"],
    }
    parity = {
        "schema_version": "hartley.h6.external_publication_parity.v1",
        "file_count": len(parity_files),
        "all_published_bytes_equal": all(row["equal"] for row in parity_files.values()),
        "files": parity_files,
    }
    parity_path = publication_root / "H6_EXTERNAL_PUBLICATION_PARITY.json"
    exclusive_json(parity_path, parity)
    copy_exclusive(manifest_path, stage_root / "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_EXTERNAL_PUBLICATION_MANIFEST.json")
    copy_exclusive(parity_path, stage_root / "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_EXTERNAL_PUBLICATION_PARITY.json")
    if not parity["all_published_bytes_equal"]:
        raise HartleyH6Error("H6 G-stage publication hash parity failed")
    return status


def _blocked_publication_sources(scratch: Path, repository: Path) -> dict[str, Path]:
    sources: dict[str, Path] = {
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml": scratch / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY_FREEZE.json": scratch / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY_FREEZE.json",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/HARTLEY_H6_EXECUTION_CONTRACT.yaml": repository / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_H6_EXECUTION_CONTRACT.yaml",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_ZERO_DEGREE_RUNNER_PARITY.json": scratch / "00_ADMIN/H6_ZERO_DEGREE_RUNNER_PARITY.json",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H5_SCRATCH_CLEANUP_LEDGER.json": scratch / "00_ADMIN/H5_SCRATCH_CLEANUP_LEDGER.json",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_STORAGE_HEALTH_READ_ONLY.json": scratch / "00_ADMIN/H6_STORAGE_HEALTH_READ_ONLY.json",
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/AGGREGATE_ATTEMPT_000002_CODE_FREEZE.json": scratch / "00_ADMIN/AGGREGATE_ATTEMPT_000002_CODE_FREEZE.json",
        "10_OBSERVABILITY/00_SEGMENT_INVENTORY/OBSERVABILITY_SEGMENT_INVENTORY.csv": scratch / "03_ANALYSIS/10_OBSERVABILITY/00_SEGMENT_INVENTORY/OBSERVABILITY_SEGMENT_INVENTORY.csv",
        "10_OBSERVABILITY/00_SEGMENT_INVENTORY/ZERO_CONTACT_PROPAGATION_ONLY_SEGMENTS.csv": scratch / "03_ANALYSIS/10_OBSERVABILITY/00_SEGMENT_INVENTORY/ZERO_CONTACT_PROPAGATION_ONLY_SEGMENTS.csv",
        "10_OBSERVABILITY/01_WINDOW_SELECTION/H6_OBSERVABILITY_WINDOW_SELECTION.csv": scratch / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION/H6_OBSERVABILITY_WINDOW_SELECTION.csv",
        "10_OBSERVABILITY/01_WINDOW_SELECTION/H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json": scratch / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION/H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json",
        "11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md": scratch / "03_ANALYSIS/11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md",
        "11_REPORT/H6_MASTER_FREEZE.json": scratch / "H6_MASTER_FREEZE.json",
    }
    for run_id, _, destination in YAW_MEMBERS:
        for name in (*COMPACT_RUN_FILES, "NATIVE_FREEZE.json"):
            sources[f"09_GAUGE_ENSEMBLE/{destination}/{name}"] = scratch / "02_FROZEN_RUNS" / run_id / name
    equivalence = scratch / "03_ANALYSIS/08_EQUIVALENCE"
    for name in (
        "GAUGE_EQUIVALENCE_EPOCH_METRICS.csv",
        "GAUGE_EQUIVALENCE_CHECKPOINT_METRICS.csv",
        "GAUGE_EQUIVALENCE_SUMMARY.csv",
        "GAUGE_NATIVE_YAW_OFFSET_SUMMARY.csv",
        "GAUGE_EQUIVALENCE_FREEZE.json",
    ):
        sources[f"09_GAUGE_ENSEMBLE/08_EQUIVALENCE/{name}"] = equivalence / name
    return sources


def publish_blocked_h6(
    scratch: Path, repository: Path, stage_root: Path, h5_anchor: Path,
) -> dict[str, Any]:
    _validate_blocked_prerequisites(scratch, repository, h5_anchor)
    status_path = scratch / "03_ANALYSIS/11_REPORT/LSE01_H6_STATUS.json"
    status = json.loads(status_path.read_text())
    master_path = scratch / "H6_MASTER_FREEZE.json"
    master = json.loads(master_path.read_text())
    if (
        status.get("terminal_status") != BLOCKED_TERMINAL
        or status.get("gauge_equivalence_pass") is not False
        or status.get("h7_authorized") is not False
        or status.get("h7_executed") is not False
        or master.get("terminal_status") != BLOCKED_TERMINAL
    ):
        raise HartleyH6Error("blocked publication status/master terminal mismatch")
    if any(status.get(key) != 0 for key in FORBIDDEN_ACCESS_COUNT_FIELDS):
        raise HartleyH6Error("blocked publication forbidden-access counters are nonzero")
    contract = master.get("tracked_execution_contract", {})
    contract_path = repository / contract.get("path", "")
    if not contract_path.is_file() or sha256_file(contract_path) != contract.get("sha256"):
        raise HartleyH6Error("blocked publication tracked execution contract changed after master freeze")
    blocked_source_files = master.get("tracked_blocked_closure_sources", {})
    for relative, identity in blocked_source_files.items():
        _require_file_identity(repository / relative, identity, f"blocked-source:{relative}")
    blocked_source_digest = hashlib.sha256(
        json.dumps(blocked_source_files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if blocked_source_digest != master.get("tracked_blocked_closure_source_manifest_sha256"):
        raise HartleyH6Error("blocked publication closure source manifest mismatch")
    for relative, identity in master.get("files", {}).items():
        _require_file_identity(scratch / relative, identity, f"master:{relative}")
    if not stage_root.is_dir() or stage_root.is_symlink():
        raise HartleyH6Error("existing LSE01 external stage root is missing/unsafe")
    if (stage_root / "09_GAUGE_ENSEMBLE").exists() or (stage_root / "10_OBSERVABILITY").exists():
        raise HartleyH6Error("H6 external destination already exists")
    sources = _blocked_publication_sources(scratch, repository)
    source_manifest: dict[str, dict[str, Any]] = {}
    for relative, source in sorted(sources.items()):
        if not source.is_file() or source.is_symlink():
            raise HartleyH6Error(f"blocked publication source missing/unsafe: {source}")
        destination = stage_root / relative
        if destination.exists() or destination.is_symlink():
            raise HartleyH6Error(f"blocked publication destination collision: {destination}")
        source_manifest[relative] = {"size": source.stat().st_size, "sha256": sha256_file(source)}
    status_destination = stage_root / "11_REPORT/LSE01_H6_STATUS.json"
    manifest_destination = stage_root / "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_EXTERNAL_PUBLICATION_MANIFEST.json"
    parity_destination = stage_root / "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_EXTERNAL_PUBLICATION_PARITY.json"
    if any(path.exists() or path.is_symlink() for path in (status_destination, manifest_destination, parity_destination)):
        raise HartleyH6Error("blocked publication control-file destination collision")

    publication_root = scratch / "04_PUBLICATION"
    publication_root.mkdir(exist_ok=False)
    manifest = {
        "schema_version": "hartley.h6.external_publication_manifest.v1",
        "terminal_status": BLOCKED_TERMINAL,
        "master_freeze_sha256": sha256_file(master_path),
        "source_file_count": len(sources), "files": source_manifest,
        "publication_mode": "EXCLUSIVE_CREATE_GUARDED_HASH_PARITY",
        "published_scientific_scope": "BLOCKED_CLOSURE_NO_REAL_OBSERVABILITY_SVD_OR_NIS_ANALYSIS",
        "g_health": "WARNING_FULL_REPAIR_NEEDED",
        "accepted_scratch_retained": True,
    }
    manifest_path = publication_root / "H6_EXTERNAL_PUBLICATION_MANIFEST.json"
    exclusive_json(manifest_path, manifest)
    for relative, source in sorted(sources.items()):
        copy_exclusive(source, stage_root / relative)

    parity_files: dict[str, Any] = {}
    for relative, identity in source_manifest.items():
        destination = stage_root / relative
        actual = {"size": destination.stat().st_size, "sha256": sha256_file(destination)}
        parity_files[relative] = {**actual, "equal": actual == identity}
    status["external_stage_published"] = True
    status["external_stage_path"] = str(stage_root)
    status["external_publication_file_count"] = len(parity_files) + 3
    status["external_publication_all_bytes_equal"] = all(row["equal"] for row in parity_files.values())
    post_status = publication_root / "LSE01_H6_STATUS.json"
    exclusive_json(post_status, status)
    copy_exclusive(post_status, status_destination)
    status_identity = {"size": post_status.stat().st_size, "sha256": sha256_file(post_status)}
    parity_files["11_REPORT/LSE01_H6_STATUS.json"] = {
        **status_identity,
        "equal": status_destination.stat().st_size == status_identity["size"]
        and sha256_file(status_destination) == status_identity["sha256"],
    }
    copy_exclusive(manifest_path, manifest_destination)
    manifest_equal = (
        manifest_destination.stat().st_size == manifest_path.stat().st_size
        and sha256_file(manifest_destination) == sha256_file(manifest_path)
    )
    parity_files["09_GAUGE_ENSEMBLE/00_CONTRACTS/H6_EXTERNAL_PUBLICATION_MANIFEST.json"] = {
        "size": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
        "equal": manifest_equal,
    }
    parity = {
        "schema_version": "hartley.h6.external_publication_parity.v1",
        "terminal_status": BLOCKED_TERMINAL,
        "file_count_excluding_this_parity_file": len(parity_files),
        "all_published_bytes_equal": all(row["equal"] for row in parity_files.values()),
        "files": parity_files,
    }
    parity_path = publication_root / "H6_EXTERNAL_PUBLICATION_PARITY.json"
    exclusive_json(parity_path, parity)
    copy_exclusive(parity_path, parity_destination)
    if (
        not parity["all_published_bytes_equal"]
        or parity_destination.stat().st_size != parity_path.stat().st_size
        or sha256_file(parity_destination) != sha256_file(parity_path)
    ):
        raise HartleyH6Error("blocked H6 G-stage publication hash parity failed")
    return status
