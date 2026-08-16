"""Phase-5 EXT05 Pavlasek IEKF C00 lifecycle.

Native solution/IMU providers and both chronological IEKF sequences are
completed and hash-frozen before this module is allowed to open the geometric
yaw audit or the same-source trace.  Independent methods may run in separate
processes; epochs inside each recursive sequence never do.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys

for _thread_variable in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"
):
    os.environ[_thread_variable] = "1"

import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml

from .ext05_pavlasek import (
    MEKF_STATUS,
    METHOD_IEKF,
    METHOD_MEKF,
    METHOD_SINGLE,
    ExtendedPose,
    PavlasekIEKF,
    finite_filter_snapshot,
    rotation_to_rpy_ned_frd_deg,
)
from .ext05_provider import (
    BASELINE_BODY_FRD_M,
    IMU_INSTALL_RPY_DEG,
    LEVER_IMU_TO_RECEIVER1_FRD_M,
    StaticCalibration,
    build_imu_only_provider,
    build_solution_position_provider,
    calibrate_static_imu,
    initial_attitude_from_gravity_and_baseline,
    sha256_file,
    verify_hash_locked_file,
)
from .shared_raw_backend import ecef_to_geodetic


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPOSITORY_ROOT / "configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml"
CLI_PATH = REPOSITORY_ROOT / "scripts/paper_rebuild/run_horizontal_literature_phase5.py"
FINAL_EVALUATOR_CONTRACT_PATH = (
    REPOSITORY_ROOT / "configs/paper_rebuild/final_v23_parity_contract.yaml"
)
DIRECT_EXT05_RUNTIME_PATHS = (
    CONTRACT_PATH,
    FINAL_EVALUATOR_CONTRACT_PATH,
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py",
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py",
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py",
    CLI_PATH,
)
MAINTAINED_SHARED_SOURCE_PATHS = (
    REPOSITORY_ROOT / "src/legsa_gins/__init__.py",
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/__init__.py",
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/manifest.py",
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/paths.py",
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/horizontal_literature/__init__.py",
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
    REPOSITORY_ROOT / "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
)
RUNTIME_SOURCE_PATHS = DIRECT_EXT05_RUNTIME_PATHS + MAINTAINED_SHARED_SOURCE_PATHS
AUDITED_SNAPSHOT_PATHS = RUNTIME_SOURCE_PATHS + (
    REPOSITORY_ROOT / "tests/paper_rebuild/test_horizontal_ext05_pavlasek.py",
    REPOSITORY_ROOT / "tests/paper_rebuild/test_horizontal_phase5_c00.py",
)
STAGE_RELATIVE = Path("stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON")
EXT05_RELATIVE = Path("06_EXT05_PAVLASEK_TWO_RECEIVER")
TRACE_EVALUATION_RELATIVE = Path("POST_NATIVE_TRACE_EVALUATION")
BASE_TIME = 1772784000.0
WINDOW_START = 66.0
WINDOW_END = 340.0
DEFAULT_WORKERS = 16
MAX_WORKERS = 20
PASS_NATIVE = "PASS_EXT05_C00_NATIVE_FROZEN_PENDING_GEOMETRIC_AUDIT"
PASS_C00 = "PASS_EXT05_C00_VALID_EXTERNAL_DUAL_RECEIVER_COMPARATOR"
BLOCKED_PREFIX = "BLOCKED_EXT05_"
EXACT_EVALUATOR_SHA256 = "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"
FROZEN_TRACE_SHA256 = "ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c"

LEFT_INVARIANT_COVARIANCE_FIELDS = tuple(
    f"P_left_{row}_{column}"
    for row in range(9)
    for column in range(row, 9)
)
NAV_FIELDS = (
    "method_id", "absolute_time_unix_seconds", "time_seconds",
    "north_m", "east_m", "down_m", "vn_mps", "ve_mps", "vd_mps",
    "roll_deg", "pitch_deg", "yaw_ned_deg",
    "covariance_coordinate", "covariance_state_order",
    "std_dtheta_x_body_deg", "std_dtheta_y_body_deg", "std_dtheta_z_body_deg",
    "std_north_m", "std_east_m", "std_down_m",
    "std_vn_mps", "std_ve_mps", "std_vd_mps",
) + LEFT_INVARIANT_COVARIANCE_FIELDS
INNOVATION_FIELDS = (
    "method_id", "provider_epoch_index", "absolute_time_unix_seconds", "time_seconds",
    "innovation_0", "innovation_1", "innovation_2",
    "innovation_3", "innovation_4", "innovation_5",
    "receiver1_residual_n", "receiver1_residual_e", "receiver1_residual_d",
    "relative_residual_n", "relative_residual_e", "relative_residual_d",
    "measured_baseline_n", "measured_baseline_e", "measured_baseline_d",
    "estimated_baseline_n", "estimated_baseline_e", "estimated_baseline_d",
    "roll_deg", "pitch_deg", "yaw_ned_deg", "nis", "degrees_of_freedom",
)
NIS_FIELDS = (
    "method_id", "provider_epoch_index", "absolute_time_unix_seconds",
    "time_seconds", "nis", "degrees_of_freedom", "normalized_nis",
)
GEOMETRIC_AUDIT_FIELDS = (
    "method_id", "provider_epoch_index", "absolute_time_unix_seconds", "time_seconds",
    "filter_yaw_ned_deg", "direct_geometric_yaw_ned_deg",
    "filter_minus_geometric_wrapsafe_deg", "absolute_yaw_difference_deg",
    "measured_baseline_n", "measured_baseline_e", "measured_baseline_d",
    "estimated_baseline_n", "estimated_baseline_e", "estimated_baseline_d",
    "measured_estimated_direction_angle_deg",
)


class Phase5RunnerError(RuntimeError):
    """EXT05 lifecycle failed closed."""


@dataclass(frozen=True)
class Phase5Paths:
    config_path: Path
    code_root: Path
    raw_root: Path
    by2_fix_root: Path
    go2_body: Path
    clean_root: Path
    by2_hash_lock: Path
    full_hash_lock: Path
    gnss1_raw: Path
    gnss2_raw: Path
    trace: Path
    stage_root: Path
    ext05_root: Path
    c00_root: Path
    report_root: Path


def _mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Phase5RunnerError(f"YAML is not an object: {path}")
    return payload


def load_paths(config_path: Path) -> Phase5Paths:
    config = Path(config_path).resolve(strict=True)
    document = _mapping(config)
    if document.get("schema_version") != "paper_rebuild.paths.v1":
        raise Phase5RunnerError("unsupported local paths schema")
    values = document.get("paths")
    if not isinstance(values, dict):
        raise Phase5RunnerError("local paths mapping is absent")
    required = ("code_root", "raw_root", "by2_fix_root", "by2_go2_body", "clean_root")
    if any(not isinstance(values.get(key), str) for key in required):
        raise Phase5RunnerError("local paths omit an EXT05 input root")
    code_root = Path(values["code_root"]).resolve(strict=True)
    if code_root != REPOSITORY_ROOT:
        raise Phase5RunnerError("configured code root is not this worktree")
    raw_root = Path(values["raw_root"]).resolve(strict=True)
    by2 = Path(values["by2_fix_root"]).resolve(strict=True)
    go2 = Path(values["by2_go2_body"]).resolve(strict=True)
    clean = Path(values["clean_root"]).resolve(strict=True)
    stage = clean / STAGE_RELATIVE
    trace = by2 / "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"
    return Phase5Paths(
        config_path=config,
        code_root=code_root,
        raw_root=raw_root,
        by2_fix_root=by2,
        go2_body=go2,
        clean_root=clean,
        by2_hash_lock=clean / "01_RAW_HASH_LOCK/BY2_HASH_LOCK.csv",
        full_hash_lock=clean / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv",
        gnss1_raw=by2 / "gnss1-raw.csv",
        gnss2_raw=by2 / "gnss2-raw.csv",
        trace=trace,
        stage_root=stage,
        ext05_root=stage / EXT05_RELATIVE,
        c00_root=stage / EXT05_RELATIVE / "C00",
        report_root=stage / "11_REPORT",
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
        handle.flush()
        os.fsync(handle.fileno())


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def _aggregate_hash(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def _wrap360_degrees(value: float) -> float:
    return value % 360.0


def _wrap180_degrees(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
    ).strip()


def _source_snapshot() -> dict[str, Any]:
    """Hash the exact dirty/untracked EXT05 source used by this native run."""

    files: dict[str, dict[str, Any]] = {}
    for path in AUDITED_SNAPSHOT_PATHS:
        if not path.is_file():
            raise Phase5RunnerError(f"EXT05 source snapshot path is absent: {path}")
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        files[relative] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "runtime_bearing": path in RUNTIME_SOURCE_PATHS,
            "source_role": (
                "DIRECT_EXT05_RUNTIME"
                if path in DIRECT_EXT05_RUNTIME_PATHS
                else "MAINTAINED_SHARED_RUNTIME"
                if path in MAINTAINED_SHARED_SOURCE_PATHS
                else "FOCUSED_TEST"
            ),
        }
    status = subprocess.check_output(
        ["git", "status", "--short", "--", *[str(path) for path in AUDITED_SNAPSHOT_PATHS]],
        cwd=REPOSITORY_ROOT,
        text=True,
    ).splitlines()
    return {
        "git_head": _git_commit(),
        "git_status_short": status,
        "git_head_alone_identifies_ext05_implementation": len(status) == 0,
        "dirty_or_untracked_snapshot_recorded": len(status) != 0,
        "file_count": len(files),
        "files": files,
    }


def _revalidate_source_snapshot(expected: Mapping[str, Any]) -> None:
    observed = _source_snapshot()
    if observed != expected:
        raise Phase5RunnerError("EXT05 source/config/test snapshot changed during native run")


def _calibration_payload(calibration: StaticCalibration) -> dict[str, Any]:
    return {
        "start_time_unix_seconds": calibration.start_time_unix_seconds,
        "end_time_unix_seconds": calibration.end_time_unix_seconds,
        "sample_count": calibration.sample_count,
        "used_preregistered_initial_interval": calibration.used_preregistered_initial_interval,
        "gyro_bias_frd_radps": calibration.gyro_bias_frd_radps.tolist(),
        "mean_specific_force_frd_mps2": calibration.mean_specific_force_frd_mps2.tolist(),
        "gyro_norm_median_radps": calibration.gyro_norm_median_radps,
        "acceleration_norm_median_mps2": calibration.acceleration_norm_median_mps2,
        "local_gravity_mps2": calibration.local_gravity_mps2,
        "max_internal_gap_seconds": calibration.max_internal_gap_seconds,
    }


def _build_cache(paths: Phase5Paths, root: Path) -> dict[str, Any]:
    positions = build_solution_position_provider(
        paths.gnss1_raw, paths.gnss2_raw,
        raw_root=paths.raw_root, by2_hash_lock=paths.by2_hash_lock,
    )
    imu, imu_report, imu_hash = build_imu_only_provider(
        paths.go2_body, raw_root=paths.raw_root, by2_hash_lock=paths.by2_hash_lock,
    )
    latitude, _longitude, height = positions.origin_geodetic_deg_m
    calibration = calibrate_static_imu(imu, latitude_deg=latitude, height_m=height)
    root.mkdir(parents=True, exist_ok=False)
    arrays = {
        "solution_times": np.asarray([epoch.absolute_time_unix_seconds for epoch in positions.epochs]),
        "solution_itow": np.asarray([epoch.itow_ms for epoch in positions.epochs], dtype=np.int64),
        "p1": np.asarray([epoch.p1_ned_m for epoch in positions.epochs]),
        "p2": np.asarray([epoch.p2_ned_m for epoch in positions.epochs]),
        "pacc1": np.asarray([epoch.pacc1_m for epoch in positions.epochs]),
        "pacc2": np.asarray([epoch.pacc2_m for epoch in positions.epochs]),
        "valid1": np.asarray([epoch.receiver1_valid for epoch in positions.epochs], dtype=np.bool_),
        "valid2": np.asarray([epoch.receiver2_valid for epoch in positions.epochs], dtype=np.bool_),
        "imu_times": np.asarray([sample.absolute_time_unix_seconds for sample in imu]),
        "gyro": np.asarray([sample.angular_rate_frd_radps for sample in imu]),
        "accel": np.asarray([sample.specific_force_frd_mps2 for sample in imu]),
    }
    array_hashes: dict[str, str] = {}
    for name, array in arrays.items():
        destination = root / f"{name}.npy"
        np.save(destination, array, allow_pickle=False)
        array_hashes[destination.name] = sha256_file(destination)
        destination.chmod(0o444)
    metadata = {
        "schema_version": "horizontal_literature.ext05.local_immutable_cache.v1",
        "position_diagnostics": positions.diagnostics,
        "imu_diagnostics": imu_report,
        "calibration": _calibration_payload(calibration),
        "origin_ecef_m": positions.origin_ecef_m.tolist(),
        "origin_geodetic_deg_m": list(positions.origin_geodetic_deg_m),
        "ecef_to_ned": positions.ecef_to_ned.tolist(),
        "source_hashes": {**positions.source_hashes, "go2_body": imu_hash},
        "array_hashes": array_hashes,
        "trace_open_count": 0,
        "provider_cache_raw_reopen_by_workers": False,
    }
    _write_json(root / "CACHE_MANIFEST.json", metadata)
    (root / "CACHE_MANIFEST.json").chmod(0o444)
    return metadata


def _load_cache(root: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    manifest = json.loads((root / "CACHE_MANIFEST.json").read_text(encoding="utf-8"))
    arrays: dict[str, np.ndarray] = {}
    for filename, expected in manifest["array_hashes"].items():
        path = root / filename
        if sha256_file(path) != expected:
            raise Phase5RunnerError("immutable provider cache hash mismatch")
        arrays[path.stem] = np.load(path, mmap_mode="r", allow_pickle=False)
    return arrays, manifest


def _nav_row(method_id: str, absolute_time: float, filter_: PavlasekIEKF) -> dict[str, Any]:
    roll, pitch, yaw = rotation_to_rpy_ned_frd_deg(filter_.pose.C_nb)
    P = filter_.covariance
    attitude_std = np.degrees(np.sqrt(np.maximum(0.0, np.diag(P[:3, :3]))))
    velocity_cov_ned = filter_.pose.C_nb @ P[3:6, 3:6] @ filter_.pose.C_nb.T
    position_cov_ned = filter_.pose.C_nb @ P[6:9, 6:9] @ filter_.pose.C_nb.T
    velocity_std = np.sqrt(np.maximum(0.0, np.diag(velocity_cov_ned)))
    position_std = np.sqrt(np.maximum(0.0, np.diag(position_cov_ned)))
    row = {
        "method_id": method_id,
        "absolute_time_unix_seconds": absolute_time,
        "time_seconds": absolute_time - BASE_TIME,
        "north_m": filter_.pose.position_ned_m[0],
        "east_m": filter_.pose.position_ned_m[1],
        "down_m": filter_.pose.position_ned_m[2],
        "vn_mps": filter_.pose.velocity_ned_mps[0],
        "ve_mps": filter_.pose.velocity_ned_mps[1],
        "vd_mps": filter_.pose.velocity_ned_mps[2],
        "roll_deg": roll, "pitch_deg": pitch, "yaw_ned_deg": yaw,
        "covariance_coordinate": "LEFT_INVARIANT_BODY_TANGENT",
        "covariance_state_order": "dtheta_x_body,dtheta_y_body,dtheta_z_body,dv_x_body,dv_y_body,dv_z_body,dr_x_body,dr_y_body,dr_z_body",
        "std_dtheta_x_body_deg": attitude_std[0],
        "std_dtheta_y_body_deg": attitude_std[1],
        "std_dtheta_z_body_deg": attitude_std[2],
        "std_north_m": position_std[0], "std_east_m": position_std[1],
        "std_down_m": position_std[2],
        "std_vn_mps": velocity_std[0], "std_ve_mps": velocity_std[1],
        "std_vd_mps": velocity_std[2],
    }
    row.update({
        f"P_left_{state_row}_{state_column}": P[state_row, state_column]
        for state_row in range(9)
        for state_column in range(state_row, 9)
    })
    return row


def _append_nav(rows: list[dict[str, Any]], row: dict[str, Any]) -> None:
    if rows and math.isclose(
        float(rows[-1]["absolute_time_unix_seconds"]),
        float(row["absolute_time_unix_seconds"]), rel_tol=0.0, abs_tol=1.0e-9,
    ):
        rows[-1] = row
    else:
        rows.append(row)


def _run_filter_sequence(
    cache_root_text: str, *, two_receiver: bool, output_root_text: str
) -> dict[str, Any]:
    """One recursive sequence; this function alone owns its chronological loop."""

    started = time.perf_counter()
    cache_root, output_root = Path(cache_root_text), Path(output_root_text)
    arrays, manifest = _load_cache(cache_root)
    calibration = manifest["calibration"]
    solution_times = arrays["solution_times"]
    imu_times = arrays["imu_times"]
    candidates = np.flatnonzero(
        (solution_times >= float(calibration["end_time_unix_seconds"]))
        & arrays["valid1"] & arrays["valid2"]
        & (solution_times <= imu_times[-1])
    )
    if candidates.size == 0:
        raise Phase5RunnerError("no valid static-initialization solution epoch")
    initial_solution_index = int(candidates[0])
    initial_time = float(solution_times[initial_solution_index])
    attitude, attitude_audit = initial_attitude_from_gravity_and_baseline(
        calibration["mean_specific_force_frd_mps2"],
        arrays["p2"][initial_solution_index] - arrays["p1"][initial_solution_index],
    )
    initial_position = (
        arrays["p1"][initial_solution_index]
        - attitude @ LEVER_IMU_TO_RECEIVER1_FRD_M
    )
    initial_covariance = np.diag(
        [math.radians(60.0) ** 2] * 3 + [0.1**2] * 3 + [0.1**2] * 3
    )
    method_id = METHOD_IEKF if two_receiver else METHOD_SINGLE
    filter_ = PavlasekIEKF(
        ExtendedPose(attitude, np.zeros(3), initial_position),
        initial_covariance,
        receiver1_from_imu_body_m=LEVER_IMU_TO_RECEIVER1_FRD_M,
        receiver2_from_receiver1_body_m=BASELINE_BODY_FRD_M,
        gyro_psd=[4.0e-4, 4.0e-4, 3.24e-4],
        accelerometer_psd=[2.89e-2, 2.25e-2, 5.76e-2],
        gravity_ned_mps2=[0.0, 0.0, float(calibration["local_gravity_mps2"])],
        two_receiver=two_receiver,
    )
    previous_imu_index = int(np.searchsorted(imu_times, initial_time, side="right") - 1)
    if previous_imu_index < 0:
        raise Phase5RunnerError("initial position precedes the Go2 IMU")
    gyro_bias = np.asarray(calibration["gyro_bias_frd_radps"], dtype=float)
    current_gyro = np.asarray(arrays["gyro"][previous_imu_index], dtype=float) - gyro_bias
    current_accel = np.asarray(arrays["accel"][previous_imu_index], dtype=float)
    imu_index = previous_imu_index + 1
    solution_index = initial_solution_index + 1
    state_time = initial_time
    nav_rows: list[dict[str, Any]] = []
    innovation_rows: list[dict[str, Any]] = []
    nis_rows: list[dict[str, Any]] = []
    _append_nav(nav_rows, _nav_row(method_id, state_time, filter_))
    processed_solution_count = 1
    invalid_solution_count = 0
    while imu_index < len(imu_times):
        next_imu = float(imu_times[imu_index])
        next_solution = (
            float(solution_times[solution_index])
            if solution_index < len(solution_times)
            and float(solution_times[solution_index]) <= float(imu_times[-1])
            else math.inf
        )
        event_time = min(next_imu, next_solution)
        dt = event_time - state_time
        if dt < -1.0e-9:
            raise Phase5RunnerError("recursive event stream is nonchronological")
        if dt > 1.0e-12:
            filter_.propagate(current_gyro, current_accel, dt)
            state_time = event_time
        if next_imu <= event_time + 1.0e-9:
            current_gyro = np.asarray(arrays["gyro"][imu_index], dtype=float) - gyro_bias
            current_accel = np.asarray(arrays["accel"][imu_index], dtype=float)
            imu_index += 1
        if next_solution <= event_time + 1.0e-9:
            index = solution_index
            solution_index += 1
            if not bool(arrays["valid1"][index]) or (two_receiver and not bool(arrays["valid2"][index])):
                invalid_solution_count += 1
            else:
                pacc1 = float(arrays["pacc1"][index])
                R1 = np.eye(3) * pacc1 * pacc1
                kwargs: dict[str, Any] = {}
                if two_receiver:
                    pacc2 = float(arrays["pacc2"][index])
                    kwargs = {
                        "receiver2_position_ned_m": arrays["p2"][index],
                        "receiver2_covariance_ned_m2": np.eye(3) * pacc2 * pacc2,
                    }
                diagnostics = filter_.update(arrays["p1"][index], R1, **kwargs)
                roll, pitch, yaw = rotation_to_rpy_ned_frd_deg(filter_.pose.C_nb)
                innovation = diagnostics.innovation.tolist() + [""] * (6 - len(diagnostics.innovation))
                relative = (
                    diagnostics.relative_residual_ned_m.tolist()
                    if diagnostics.relative_residual_ned_m is not None else ["", "", ""]
                )
                estimated = (
                    (filter_.pose.C_nb @ BASELINE_BODY_FRD_M).tolist()
                    if two_receiver else ["", "", ""]
                )
                measured = (
                    (arrays["p2"][index] - arrays["p1"][index]).tolist()
                    if two_receiver else ["", "", ""]
                )
                innovation_rows.append({
                    "method_id": method_id, "provider_epoch_index": index,
                    "absolute_time_unix_seconds": state_time,
                    "time_seconds": state_time - BASE_TIME,
                    **{f"innovation_{axis}": innovation[axis] for axis in range(6)},
                    "receiver1_residual_n": diagnostics.receiver1_residual_ned_m[0],
                    "receiver1_residual_e": diagnostics.receiver1_residual_ned_m[1],
                    "receiver1_residual_d": diagnostics.receiver1_residual_ned_m[2],
                    "relative_residual_n": relative[0], "relative_residual_e": relative[1],
                    "relative_residual_d": relative[2],
                    "measured_baseline_n": measured[0], "measured_baseline_e": measured[1],
                    "measured_baseline_d": measured[2],
                    "estimated_baseline_n": estimated[0], "estimated_baseline_e": estimated[1],
                    "estimated_baseline_d": estimated[2],
                    "roll_deg": roll, "pitch_deg": pitch, "yaw_ned_deg": yaw,
                    "nis": diagnostics.nis,
                    "degrees_of_freedom": 6 if two_receiver else 3,
                })
                nis_rows.append({
                    "method_id": method_id, "provider_epoch_index": index,
                    "absolute_time_unix_seconds": state_time,
                    "time_seconds": state_time - BASE_TIME,
                    "nis": diagnostics.nis,
                    "degrees_of_freedom": 6 if two_receiver else 3,
                    "normalized_nis": diagnostics.nis / (6 if two_receiver else 3),
                })
                processed_solution_count += 1
        _append_nav(nav_rows, _nav_row(method_id, state_time, filter_))
    beyond_support = int(np.sum(solution_times > imu_times[-1]))
    if beyond_support != 38:
        raise Phase5RunnerError("provider epochs beyond IMU support are not the audited 38")
    if any(
        float(later["absolute_time_unix_seconds"]) <= float(earlier["absolute_time_unix_seconds"])
        for earlier, later in zip(nav_rows, nav_rows[1:])
    ):
        raise Phase5RunnerError("NAV output is not strictly chronological")
    output_root.mkdir(parents=True, exist_ok=False)
    nav_path = output_root / "NAV.csv"
    innovation_path = output_root / "INNOVATION.csv"
    nis_path = output_root / "NIS.csv"
    _write_csv(nav_path, NAV_FIELDS, nav_rows)
    _write_csv(innovation_path, INNOVATION_FIELDS, innovation_rows)
    _write_csv(nis_path, NIS_FIELDS, nis_rows)
    snapshot = finite_filter_snapshot(filter_)
    if (
        not snapshot["finite"]
        or snapshot["rotation_orthogonality_error"] > 1.0e-10
        or abs(snapshot["rotation_determinant"] - 1.0) > 1.0e-10
        or snapshot["minimum_covariance_eigenvalue"] < -1.0e-8
    ):
        raise Phase5RunnerError("final filter state/covariance consistency failed")
    summary = {
        "method_id": method_id,
        "two_receiver": two_receiver,
        "initial_solution_index": initial_solution_index,
        "initial_time_unix_seconds": initial_time,
        "initial_attitude": attitude_audit,
        "initial_position_ned_m": initial_position.tolist(),
        "initial_velocity_ned_mps": [0.0, 0.0, 0.0],
        "processed_solution_count": processed_solution_count,
        "invalid_solution_count": invalid_solution_count,
        "provider_epochs_beyond_imu_support": beyond_support,
        "nav_row_count": len(nav_rows),
        "innovation_row_count": len(innovation_rows),
        "nis_row_count": len(nis_rows),
        "final_snapshot": snapshot,
        "trace_open_count": 0,
        "recursive_epochs_chronological": True,
    }
    summary_path = output_root / "SCIENTIFIC_SUMMARY.json"
    _write_json(summary_path, summary)
    scientific_paths = (nav_path, innovation_path, nis_path, summary_path)
    return {
        "method_id": method_id,
        "output_root": str(output_root),
        "sequence_process_id": os.getpid(),
        "scientific_hash": _aggregate_hash(scientific_paths),
        "file_hashes": {path.name: sha256_file(path) for path in scientific_paths},
        "summary": summary,
        "runtime_seconds": time.perf_counter() - started,
    }


def _run_method_set(cache_root: Path, root: Path, workers: int) -> dict[str, dict[str, Any]]:
    tasks = ((True, "dual"), (False, "single"))
    if workers == 1:
        return {
            name: _run_filter_sequence(str(cache_root), two_receiver=dual, output_root_text=str(root / name))
            for dual, name in tasks
        }
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            name: executor.submit(
                _run_filter_sequence, str(cache_root), two_receiver=dual,
                output_root_text=str(root / name),
            )
            for dual, name in tasks
        }
        return {name: future.result() for name, future in futures.items()}


def _copy_exclusive(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_handle, destination.open("xb") as output_handle:
        shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
        output_handle.flush()
        os.fsync(output_handle.fileno())
    if sha256_file(source) != sha256_file(destination):
        raise Phase5RunnerError("DrvFS output copy hash mismatch")


def _combine_csv(paths: Sequence[Path], destination: Path, fields: Sequence[str]) -> None:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    _write_csv(destination, fields, rows)


def _flatten(prefix: str, value: Any) -> Iterable[dict[str, str]]:
    if isinstance(value, Mapping):
        for key in sorted(value):
            yield from _flatten(f"{prefix}.{key}" if prefix else str(key), value[key])
    else:
        yield {"field": prefix, "value_json": json.dumps(value, sort_keys=True, allow_nan=False)}


IEKF_NAV_NAME = "EXT05A_C00_IEKF_NAV.csv"
IEKF_INNOVATION_NAME = "EXT05A_C00_INNOVATION_DIAGNOSTICS.csv"
IEKF_NIS_NAME = "EXT05A_C00_NIS_DIAGNOSTICS.csv"
PROVIDER_DIAGNOSTICS_NAME = "EXT05A_C00_PROVIDER_DIAGNOSTICS.csv"
RUNTIME_NAME = "EXT05A_C00_RUNTIME.csv"
NATIVE_SUMMARY_NAME = "EXT05A_C00_NATIVE_SUMMARY.json"
SINGLE_NAV_NAME = "EXT05C_C00_SINGLE_RECEIVER_IEKF_NAV.csv"
SINGLE_INNOVATION_NAME = "EXT05C_C00_SINGLE_RECEIVER_IEKF_INNOVATION_DIAGNOSTICS.csv"
SINGLE_NIS_NAME = "EXT05C_C00_SINGLE_RECEIVER_IEKF_NIS_DIAGNOSTICS.csv"
MEKF_WAIVER_NAME = "EXT05B_C00_MEKF_NOT_IMPLEMENTED.json"
NATIVE_FREEZE_NAME = "EXT05A_C00_NATIVE_FREEZE.json"

NATIVE_NAMES = (
    IEKF_NAV_NAME,
    IEKF_INNOVATION_NAME,
    IEKF_NIS_NAME,
    PROVIDER_DIAGNOSTICS_NAME,
    RUNTIME_NAME,
    NATIVE_SUMMARY_NAME,
    SINGLE_NAV_NAME,
    SINGLE_INNOVATION_NAME,
    SINGLE_NIS_NAME,
    MEKF_WAIVER_NAME,
)


def _validate_native_freeze(c00_root: Path) -> dict[str, Any]:
    freeze_path = c00_root / NATIVE_FREEZE_NAME
    if not freeze_path.is_file():
        raise Phase5RunnerError("native freeze is absent")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    for name, evidence in freeze.get("files", {}).items():
        path = c00_root / name
        if not path.is_file() or sha256_file(path) != evidence.get("sha256") or path.stat().st_size != evidence.get("size_bytes"):
            raise Phase5RunnerError(f"native freeze revalidation failed: {name}")
    if set(freeze.get("files", {})) != set(NATIVE_NAMES):
        raise Phase5RunnerError("native freeze file set drifted")
    if freeze.get("trace_open_count") != 0:
        raise Phase5RunnerError("native freeze records a trace open")
    return freeze


def run_native(paths: Phase5Paths, *, workers: int = DEFAULT_WORKERS, resume: bool = False) -> dict[str, Any]:
    if workers != DEFAULT_WORKERS:
        raise Phase5RunnerError("EXT05A C00 determinism gate requires exactly 16 workers")
    if paths.c00_root.exists():
        if resume:
            _validate_native_freeze(paths.c00_root)
            return json.loads((paths.c00_root / NATIVE_SUMMARY_NAME).read_text(encoding="utf-8"))
        raise Phase5RunnerError("EXT05 C00 output root already exists; use --resume")
    native_start_unix_seconds = time.time()
    native_start_utc = datetime.fromtimestamp(
        native_start_unix_seconds, timezone.utc
    ).isoformat()
    source_snapshot = _source_snapshot()
    with tempfile.TemporaryDirectory(prefix="legsa_ext05_c00_") as temporary:
        temporary_root = Path(temporary)
        cache_root = temporary_root / "immutable_provider_cache"
        cache_manifest = _build_cache(paths, cache_root)
        probe1 = _run_method_set(cache_root, temporary_root / "workers1", 1)
        probe16 = _run_method_set(cache_root, temporary_root / "workers16", 16)
        deterministic = {
            name: probe1[name]["scientific_hash"] == probe16[name]["scientific_hash"]
            for name in ("dual", "single")
        }
        if not all(deterministic.values()):
            raise Phase5RunnerError("workers 1/16 scientific outputs differ")
        _revalidate_source_snapshot(source_snapshot)
        paths.c00_root.mkdir(parents=True, exist_ok=False)
        dual_root = Path(probe16["dual"]["output_root"])
        single_root = Path(probe16["single"]["output_root"])
        _copy_exclusive(dual_root / "NAV.csv", paths.c00_root / IEKF_NAV_NAME)
        _copy_exclusive(dual_root / "INNOVATION.csv", paths.c00_root / IEKF_INNOVATION_NAME)
        _copy_exclusive(dual_root / "NIS.csv", paths.c00_root / IEKF_NIS_NAME)
        _copy_exclusive(single_root / "NAV.csv", paths.c00_root / SINGLE_NAV_NAME)
        _copy_exclusive(
            single_root / "INNOVATION.csv", paths.c00_root / SINGLE_INNOVATION_NAME
        )
        _copy_exclusive(single_root / "NIS.csv", paths.c00_root / SINGLE_NIS_NAME)
        provider_evidence = {
            "position": cache_manifest["position_diagnostics"],
            "imu": cache_manifest["imu_diagnostics"],
            "calibration": cache_manifest["calibration"],
            "source_hashes": cache_manifest["source_hashes"],
            "cache_manifest_sha256": sha256_file(cache_root / "CACHE_MANIFEST.json"),
            "cache_location": "LINUX_LOCAL_TEMPORARY_REMOVED_AFTER_NATIVE_FINALIZATION",
        }
        _write_csv(
            paths.c00_root / PROVIDER_DIAGNOSTICS_NAME, ("field", "value_json"),
            _flatten("", provider_evidence),
        )
        _write_csv(
            paths.c00_root / RUNTIME_NAME,
            (
                "method_id", "run_variant", "status", "process_pool_max_workers",
                "submitted_recursive_sequences", "sequence_process_id",
                "recursive_epoch_parallelism", "runtime_seconds",
            ),
            [
                {"method_id": METHOD_IEKF, "run_variant": "WORKERS_1", "status": "COMPLETE", "process_pool_max_workers": 1, "submitted_recursive_sequences": 2, "sequence_process_id": probe1["dual"]["sequence_process_id"], "recursive_epoch_parallelism": False, "runtime_seconds": probe1["dual"]["runtime_seconds"]},
                {"method_id": METHOD_SINGLE, "run_variant": "WORKERS_1", "status": "COMPLETE", "process_pool_max_workers": 1, "submitted_recursive_sequences": 2, "sequence_process_id": probe1["single"]["sequence_process_id"], "recursive_epoch_parallelism": False, "runtime_seconds": probe1["single"]["runtime_seconds"]},
                {"method_id": METHOD_IEKF, "run_variant": "WORKERS_16", "status": "COMPLETE", "process_pool_max_workers": 16, "submitted_recursive_sequences": 2, "sequence_process_id": probe16["dual"]["sequence_process_id"], "recursive_epoch_parallelism": False, "runtime_seconds": probe16["dual"]["runtime_seconds"]},
                {"method_id": METHOD_SINGLE, "run_variant": "WORKERS_16", "status": "COMPLETE", "process_pool_max_workers": 16, "submitted_recursive_sequences": 2, "sequence_process_id": probe16["single"]["sequence_process_id"], "recursive_epoch_parallelism": False, "runtime_seconds": probe16["single"]["runtime_seconds"]},
                {"method_id": METHOD_MEKF, "run_variant": "WAIVED", "status": MEKF_STATUS, "process_pool_max_workers": 0, "submitted_recursive_sequences": 0, "sequence_process_id": "", "recursive_epoch_parallelism": False, "runtime_seconds": 0.0},
            ],
        )
        _write_json(paths.c00_root / MEKF_WAIVER_NAME, {
            "method_id": METHOD_MEKF,
            "status": MEKF_STATUS,
            "human_waiver": True,
            "paper_identity_count": 1,
            "separate_paper_claim": False,
            "defects": _mapping(CONTRACT_PATH)["methods"]["appendix_baseline"]["defects"],
        })
        native_end_unix_seconds = time.time()
        summary = {
            "schema_version": "horizontal_literature.ext05.c00.native_summary.v1",
            "terminal_status": PASS_NATIVE,
            "paper": _mapping(CONTRACT_PATH)["paper"],
            "equation_to_code": _mapping(CONTRACT_PATH)["equation_to_code"],
            "methods": {
                METHOD_IEKF: probe16["dual"]["summary"],
                METHOD_MEKF: {"status": MEKF_STATUS, "scientific_nav_row_count": 0},
                METHOD_SINGLE: probe16["single"]["summary"],
            },
            "worker_determinism": {
                "workers_1_vs_16_identical": all(deterministic.values()),
                "per_method": deterministic,
                "workers1_scientific_hashes": {name: probe1[name]["scientific_hash"] for name in deterministic},
                "workers16_scientific_hashes": {name: probe16[name]["scientific_hash"] for name in deterministic},
                "recursive_epoch_parallelism": False,
            },
            "execution": {
                "argv": list(sys.argv),
                "main_process_id": os.getpid(),
                "native_start_unix_seconds": native_start_unix_seconds,
                "native_start_utc": native_start_utc,
                "native_output_finalization_unix_seconds": native_end_unix_seconds,
                "native_output_finalization_utc": datetime.fromtimestamp(
                    native_end_unix_seconds, timezone.utc
                ).isoformat(),
                "workers1_sequence_process_ids": {
                    name: probe1[name]["sequence_process_id"] for name in ("dual", "single")
                },
                "workers16_sequence_process_ids": {
                    name: probe16[name]["sequence_process_id"] for name in ("dual", "single")
                },
                "workers16_process_pool_max_workers": 16,
                "workers16_submitted_recursive_sequences": 2,
                "thread_environment": {
                    name: os.environ[name]
                    for name in (
                        "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                        "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                    )
                },
            },
            "provider": provider_evidence,
            "data_mode": "real_by2_raw",
            "synthetic_data_used": False,
            "semisynthetic_data_used": False,
            "trace_used_online": False,
            "trace_open_count": 0,
            "receiver_imu_as_body_imu": False,
            "go2_quaternion_rpy_yaw_input": False,
            "A1_status_yaw_input": False,
            "EXT01_EXT04_output_input": False,
            "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False,
            "per_case_tuning": False,
            "output_only_correction": False,
            "epoch_deleted_for_metric": False,
            "old_runtime_input_count": 0,
            "code_commit": source_snapshot["git_head"],
            "code_snapshot": source_snapshot,
            "code_snapshot_revalidated_before_output_finalization": True,
            "config_hash": sha256_file(CONTRACT_PATH),
            "native_files_mutable_after_freeze": False,
        }
        _write_json(paths.c00_root / NATIVE_SUMMARY_NAME, summary)
        _revalidate_source_snapshot(source_snapshot)
        file_evidence = {
            name: {"sha256": sha256_file(paths.c00_root / name), "size_bytes": (paths.c00_root / name).stat().st_size}
            for name in NATIVE_NAMES
        }
        freeze = {
            "schema_version": "horizontal_literature.ext05.c00.native_freeze.v1",
            "terminal_status": PASS_NATIVE,
            "files": file_evidence,
            "trace_open_count": 0,
            "HPPOSECEF_solver_input": True,
            "status_A1_yaw_solver_input": False,
            "go2_quaternion_rpy_yaw_input": False,
            "EXT01_EXT04_output_input": False,
            "LegSA_output_input": False,
            "scientific_hash_workers_1_vs_16_identical": True,
            "code_commit": summary["code_commit"],
            "code_snapshot": source_snapshot,
            "code_snapshot_revalidated_immediately_before_freeze": True,
            "config_hash": summary["config_hash"],
        }
        _write_json(paths.c00_root / NATIVE_FREEZE_NAME, freeze)
        _validate_native_freeze(paths.c00_root)
        return summary


def _finite_csv_float(row: Mapping[str, str], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise Phase5RunnerError(f"native diagnostic has invalid {field}") from exc
    if not math.isfinite(value):
        raise Phase5RunnerError(f"native diagnostic has nonfinite {field}")
    return value


def _geometric_audit_rows(
    innovation_rows: Sequence[Mapping[str, str]], *, initial_time: float,
) -> list[dict[str, Any]]:
    """Compare frozen IEKF yaw with the direct P2-P1 physical transform."""

    cutoff = initial_time + 5.0
    output: list[dict[str, Any]] = []
    last_time = -math.inf
    for source in innovation_rows:
        if source.get("method_id") != METHOD_IEKF:
            continue
        absolute_time = _finite_csv_float(source, "absolute_time_unix_seconds")
        if absolute_time <= last_time:
            raise Phase5RunnerError("dual-receiver innovation rows are nonchronological")
        last_time = absolute_time
        if absolute_time < cutoff:
            continue
        measured = np.asarray([
            _finite_csv_float(source, "measured_baseline_n"),
            _finite_csv_float(source, "measured_baseline_e"),
            _finite_csv_float(source, "measured_baseline_d"),
        ])
        estimated = np.asarray([
            _finite_csv_float(source, "estimated_baseline_n"),
            _finite_csv_float(source, "estimated_baseline_e"),
            _finite_csv_float(source, "estimated_baseline_d"),
        ])
        for field in (
            "receiver1_residual_n", "receiver1_residual_e", "receiver1_residual_d",
            "relative_residual_n", "relative_residual_e", "relative_residual_d",
        ):
            _finite_csv_float(source, field)
        measured_horizontal = math.hypot(float(measured[0]), float(measured[1]))
        estimated_horizontal = math.hypot(float(estimated[0]), float(estimated[1]))
        if measured_horizontal <= 0.1 or estimated_horizontal <= 0.1:
            raise Phase5RunnerError("geometric audit baseline has inadequate horizontal length")
        geometric_yaw = _wrap360_degrees(
            math.degrees(math.atan2(float(measured[1]), float(measured[0]))) + 90.0
        )
        filter_yaw = _finite_csv_float(source, "yaw_ned_deg")
        yaw_difference = _wrap180_degrees(filter_yaw - geometric_yaw)
        measured_norm = float(np.linalg.norm(measured))
        estimated_norm = float(np.linalg.norm(estimated))
        cosine = float(np.clip(
            np.dot(measured, estimated) / (measured_norm * estimated_norm), -1.0, 1.0
        ))
        direction_angle = math.degrees(math.acos(cosine))
        output.append({
            "method_id": METHOD_IEKF,
            "provider_epoch_index": int(source["provider_epoch_index"]),
            "absolute_time_unix_seconds": absolute_time,
            "time_seconds": absolute_time - BASE_TIME,
            "filter_yaw_ned_deg": filter_yaw,
            "direct_geometric_yaw_ned_deg": geometric_yaw,
            "filter_minus_geometric_wrapsafe_deg": yaw_difference,
            "absolute_yaw_difference_deg": abs(yaw_difference),
            "measured_baseline_n": measured[0],
            "measured_baseline_e": measured[1],
            "measured_baseline_d": measured[2],
            "estimated_baseline_n": estimated[0],
            "estimated_baseline_e": estimated[1],
            "estimated_baseline_d": estimated[2],
            "measured_estimated_direction_angle_deg": direction_angle,
        })
    if not output:
        raise Phase5RunnerError("geometric audit has no post-transient IEKF rows")
    return output


def _native_yaw_continuity(c00_root: Path) -> dict[str, Any]:
    with (c00_root / IEKF_NAV_NAME).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    times = np.asarray([_finite_csv_float(row, "absolute_time_unix_seconds") for row in rows])
    yaw = np.asarray([_finite_csv_float(row, "yaw_ned_deg") for row in rows])
    if len(rows) < 2 or np.any(np.diff(times) <= 0.0):
        raise Phase5RunnerError("frozen IEKF NAV is not strictly chronological")
    differences = np.asarray([
        _wrap180_degrees(float(later - earlier))
        for earlier, later in zip(yaw, yaw[1:])
    ])
    maximum = float(np.max(np.abs(differences)))
    return {
        "nav_row_count": len(rows),
        "maximum_adjacent_wrapsafe_yaw_step_deg": maximum,
        "adjacent_wrapsafe_yaw_step_ge_90_count": int(np.sum(np.abs(differences) >= 90.0)),
        "no_180_degree_representation_discontinuity": bool(maximum < 90.0),
    }


def run_geometric_audit(paths: Phase5Paths, *, resume: bool = False) -> dict[str, Any]:
    """Audit direct baseline yaw only after immutable native-output validation."""

    freeze_before = _validate_native_freeze(paths.c00_root)
    audit_root = paths.c00_root / "POST_NATIVE_GEOMETRIC_AUDIT"
    summary_path = audit_root / "EXT05A_C00_GEOMETRIC_YAW_AUDIT.json"
    rows_path = audit_root / "EXT05A_C00_GEOMETRIC_YAW_AUDIT.csv"
    if audit_root.exists():
        if not resume or not summary_path.is_file() or not rows_path.is_file():
            raise Phase5RunnerError("geometric audit output already exists or is incomplete")
        _validate_native_freeze(paths.c00_root)
        return json.loads(summary_path.read_text(encoding="utf-8"))

    native_summary = json.loads(
        (paths.c00_root / NATIVE_SUMMARY_NAME).read_text(encoding="utf-8")
    )
    initial_time = float(native_summary["methods"][METHOD_IEKF]["initial_time_unix_seconds"])
    with (paths.c00_root / IEKF_INNOVATION_NAME).open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        innovation_rows = list(csv.DictReader(handle))
    rows = _geometric_audit_rows(innovation_rows, initial_time=initial_time)
    absolute = np.asarray([float(row["absolute_yaw_difference_deg"]) for row in rows])
    direction = np.asarray([
        float(row["measured_estimated_direction_angle_deg"]) for row in rows
    ])
    continuity = _native_yaw_continuity(paths.c00_root)
    median = float(np.median(absolute))
    p95 = float(np.percentile(absolute, 95.0))
    thresholds_pass = median <= 10.0 and p95 <= 30.0
    implementation_consistent = thresholds_pass and bool(
        continuity["no_180_degree_representation_discontinuity"]
    )
    status = (
        PASS_C00
        if implementation_consistent
        else "BLOCKED_EXT05_FRAME_SIGN_STATE_UPDATE_GEOMETRIC_AUDIT"
    )
    audit_root.mkdir(parents=True, exist_ok=False)
    _write_csv(rows_path, GEOMETRIC_AUDIT_FIELDS, rows)
    summary = {
        "schema_version": "horizontal_literature.ext05.c00.geometric_yaw_audit.v1",
        "terminal_status": status,
        "audit_role": "POST_NATIVE_IMPLEMENTATION_AUDIT_NOT_REFERENCE_EVALUATION",
        "native_freeze_sha256": sha256_file(paths.c00_root / NATIVE_FREEZE_NAME),
        "native_file_count_revalidated": len(freeze_before["files"]),
        "trace_open_count": 0,
        "trace_used": False,
        "sign_time_offset_search_used": False,
        "initial_transient_skipped_seconds": 5.0,
        "audited_update_count": len(rows),
        "median_absolute_iekf_vs_geometric_yaw_difference_deg": median,
        "p95_absolute_iekf_vs_geometric_yaw_difference_deg": p95,
        "maximum_absolute_iekf_vs_geometric_yaw_difference_deg": float(np.max(absolute)),
        "median_measured_vs_estimated_3d_direction_angle_deg": float(np.median(direction)),
        "p95_measured_vs_estimated_3d_direction_angle_deg": float(np.percentile(direction, 95.0)),
        "thresholds_deg": {"median_max": 10.0, "p95_max": 30.0},
        "thresholds_pass": thresholds_pass,
        "continuity": continuity,
        "native_files_unchanged_after_audit": False,
    }
    _write_json(summary_path, summary)
    freeze_after = _validate_native_freeze(paths.c00_root)
    if freeze_after != freeze_before:
        raise Phase5RunnerError("native freeze changed during geometric audit")
    summary["native_files_unchanged_after_audit"] = True
    # Replace the just-created summary without weakening exclusive creation for
    # the artifact lifecycle: write a sibling, fsync, then atomically replace it.
    replacement = audit_root / ".EXT05A_C00_GEOMETRIC_YAW_AUDIT.json.tmp"
    _write_json(replacement, summary)
    os.replace(replacement, summary_path)
    return summary


def _materialize_exact_evaluator_nav(
    native_nav: Path,
    destination: Path,
    *,
    origin_ecef_m: Sequence[float],
    ecef_to_ned: Sequence[Sequence[float]],
) -> dict[str, Any]:
    """Adapt frozen local-NED NAV to the exact evaluator's 11-column LLA NAV."""

    origin = np.asarray(origin_ecef_m, dtype=float)
    rotation = np.asarray(ecef_to_ned, dtype=float)
    if origin.shape != (3,) or rotation.shape != (3, 3):
        raise Phase5RunnerError("evaluation adapter fixed NED frame is invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    times: list[float] = []
    with native_nav.open("r", encoding="utf-8", newline="") as input_handle:
        reader = csv.DictReader(input_handle)
        with destination.open("x", encoding="utf-8", newline="\n") as output_handle:
            output_handle.write("% index time lat_deg lon_deg height_m vn ve vd roll pitch yaw\n")
            for index, row in enumerate(reader):
                time_seconds = _finite_csv_float(row, "time_seconds")
                if not WINDOW_START <= time_seconds <= WINDOW_END:
                    continue
                ned = np.asarray([
                    _finite_csv_float(row, "north_m"),
                    _finite_csv_float(row, "east_m"),
                    _finite_csv_float(row, "down_m"),
                ])
                receiver_ecef = origin + rotation.T @ ned
                latitude, longitude, height = ecef_to_geodetic(receiver_ecef)
                values = (
                    index,
                    time_seconds,
                    math.degrees(latitude),
                    math.degrees(longitude),
                    height,
                    _finite_csv_float(row, "vn_mps"),
                    _finite_csv_float(row, "ve_mps"),
                    _finite_csv_float(row, "vd_mps"),
                    _finite_csv_float(row, "roll_deg"),
                    _finite_csv_float(row, "pitch_deg"),
                    _finite_csv_float(row, "yaw_ned_deg"),
                )
                output_handle.write(" ".join(
                    str(value) if isinstance(value, int) else format(value, ".17g")
                    for value in values
                ) + "\n")
                times.append(time_seconds)
            output_handle.flush()
            os.fsync(output_handle.fileno())
    if len(times) < 2 or any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise Phase5RunnerError("evaluation adapter NAV is empty or nonchronological")
    differences = np.diff(np.asarray(times))
    return {
        "input_native_nav_sha256": sha256_file(native_nav),
        "evaluator_nav_sha256": sha256_file(destination),
        "output_epoch_count": len(times),
        "time_start_seconds": times[0],
        "time_end_seconds": times[-1],
        "strictly_chronological": True,
        "median_dt_seconds": float(np.median(differences)),
        "p99_dt_seconds": float(np.percentile(differences, 99.0)),
        "maximum_dt_seconds": float(np.max(differences)),
        "nonpositive_dt_count": 0,
        "window_seconds": [WINDOW_START, WINDOW_END],
        "window_selection": "CLOSED_FIXED_NATIVE_TIME_NO_ERROR_SELECTION",
        "position_conversion": "fixed_NED_to_ECEF_to_WGS84_geodetic",
    }


def _metric_distribution(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0 or np.any(~np.isfinite(array)):
        raise Phase5RunnerError("offline metric vector is empty or nonfinite")
    absolute = np.abs(array)
    return {
        "rmse": float(np.sqrt(np.mean(array * array))),
        "mae": float(np.mean(absolute)),
        "median_absolute": float(np.median(absolute)),
        "p95_absolute": float(np.percentile(absolute, 95.0)),
        "p99_absolute": float(np.percentile(absolute, 99.0)),
        "maximum_absolute": float(np.max(absolute)),
    }


def _nis_distribution(native_nis: Path) -> dict[str, Any]:
    with native_nis.open("r", encoding="utf-8", newline="") as handle:
        rows = [
            row for row in csv.DictReader(handle)
            if WINDOW_START <= _finite_csv_float(row, "time_seconds") <= WINDOW_END
        ]
    nis = np.asarray([_finite_csv_float(row, "nis") for row in rows])
    normalized = np.asarray([_finite_csv_float(row, "normalized_nis") for row in rows])
    if not rows or np.any(nis < 0.0):
        raise Phase5RunnerError("native NIS window is empty or negative")
    dof = sorted({int(row["degrees_of_freedom"]) for row in rows})
    if len(dof) != 1:
        raise Phase5RunnerError("native NIS degrees of freedom drifted")
    return {
        "row_count": len(rows),
        "degrees_of_freedom": dof[0],
        "nis": _metric_distribution(nis),
        "normalized_nis": _metric_distribution(normalized),
        "native_nis_sha256": sha256_file(native_nis),
    }


def _run_verified_exact_evaluator(
    *,
    evaluator: Path,
    trace: Path,
    nav: Path,
    method_root: Path,
) -> dict[str, Any]:
    output = method_root / "EXACT_EVALUATOR_OUTPUT"
    strace_path = method_root / "EXACT_EVALUATOR_TRACE_OPEN.raw"
    command = [
        "strace", "-f", "-qq", "-s", "4096", "-e", "trace=openat",
        "-P", str(trace), "-P", str(nav), "-P", str(evaluator),
        "-o", str(strace_path),
        sys.executable, str(evaluator),
        "--trace", str(trace), "--nav", str(nav), "--outdir", str(output),
        "--base_time", format(BASE_TIME, ".1f"), "--yaw_truth_mode", "enu",
    ]
    environment = os.environ.copy()
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[name] = "1"
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180.0,
        check=False,
    )
    runtime = time.perf_counter() - started
    _write_text(method_root / "EXACT_EVALUATOR_STDOUT.txt", result.stdout)
    _write_text(method_root / "EXACT_EVALUATOR_STDERR.txt", result.stderr)
    if result.returncode != 0:
        raise Phase5RunnerError(
            f"exact evaluator exited {result.returncode}: {result.stderr[-500:]}"
        )
    trace_lines = strace_path.read_text(encoding="utf-8", errors="strict").splitlines()
    trace_open_count = sum(
        "openat(" in line and trace.name in line for line in trace_lines
    )
    nav_open_count = sum("openat(" in line and nav.name in line for line in trace_lines)
    evaluator_open_count = sum(
        "openat(" in line and evaluator.name in line for line in trace_lines
    )
    if trace_open_count <= 0:
        raise Phase5RunnerError("strace did not prove the exact evaluator opened trace")
    if nav_open_count <= 0 or evaluator_open_count <= 0:
        raise Phase5RunnerError("strace omitted exact evaluator or adapted NAV open")
    summary_path = output / "summary.json"
    errors_path = output / "error_series.csv"
    if not summary_path.is_file() or not errors_path.is_file():
        raise Phase5RunnerError("exact evaluator omitted required outputs")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    meta = summary.get("meta", {})
    if (
        float(meta.get("base_time", math.nan)) != BASE_TIME
        or meta.get("yaw_truth_mode") != "enu"
        or int(meta.get("num_samples", 0)) <= 0
    ):
        raise Phase5RunnerError("exact evaluator summary violates time/yaw contract")
    return {
        "command": command,
        "returncode": result.returncode,
        "runtime_seconds": runtime,
        "trace_open_count": trace_open_count,
        "nav_open_count": nav_open_count,
        "evaluator_open_count": evaluator_open_count,
        "strace_sha256": sha256_file(strace_path),
        "summary_sha256": sha256_file(summary_path),
        "error_series_sha256": sha256_file(errors_path),
        "summary": summary,
        "summary_path": summary_path,
        "errors_path": errors_path,
    }


def _supplement_exact_metrics(
    *,
    method_id: str,
    evaluator_result: Mapping[str, Any],
    adapter: Mapping[str, Any],
    nis: Mapping[str, Any],
    native_runtime_seconds: float,
) -> dict[str, Any]:
    with Path(evaluator_result["errors_path"]).open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        error_rows = list(csv.DictReader(handle))
    if not error_rows:
        raise Phase5RunnerError("exact evaluator error series is empty")
    columns = {
        "north_m": "err_n_m",
        "east_m": "err_e_m",
        "up_m": "err_u_m",
        "horizontal_m": "horizontal_err_m",
        "position_3d_m": "position_3d_err_m",
        "roll_deg": "roll_err_deg",
        "pitch_deg": "pitch_err_deg",
        "yaw_deg": "yaw_err_deg",
    }
    metrics = {
        name: _metric_distribution([
            _finite_csv_float(row, column) for row in error_rows
        ])
        for name, column in columns.items()
    }
    exact = evaluator_result["summary"]
    crosschecks = {
        "north_rmse": abs(metrics["north_m"]["rmse"] - float(exact["position"]["north_rmse_m"])),
        "east_rmse": abs(metrics["east_m"]["rmse"] - float(exact["position"]["east_rmse_m"])),
        "up_rmse": abs(metrics["up_m"]["rmse"] - float(exact["position"]["up_rmse_m"])),
        "horizontal_rmse": abs(metrics["horizontal_m"]["rmse"] - float(exact["position"]["horizontal_rmse_m"])),
        "position_3d_rmse": abs(metrics["position_3d_m"]["rmse"] - float(exact["position"]["position_3d_rmse_m"])),
        "roll_rmse": abs(metrics["roll_deg"]["rmse"] - float(exact["attitude"]["roll_rmse_deg"])),
        "pitch_rmse": abs(metrics["pitch_deg"]["rmse"] - float(exact["attitude"]["pitch_rmse_deg"])),
        "yaw_rmse": abs(metrics["yaw_deg"]["rmse"] - float(exact["attitude"]["yaw_rmse_deg"])),
    }
    if max(crosschecks.values()) > 1.0e-10:
        raise Phase5RunnerError("supplemental metrics do not reproduce exact evaluator RMSE")
    output_count = int(adapter["output_epoch_count"])
    matched = len(error_rows)
    if matched > output_count:
        raise Phase5RunnerError("exact evaluator matched more epochs than adapter supplied")
    error_times = np.asarray([_finite_csv_float(row, "time") for row in error_rows])
    if np.any(np.diff(error_times) <= 0.0):
        raise Phase5RunnerError("exact evaluator error series is nonchronological")
    return {
        "method_id": method_id,
        "status": "EVALUATED_SAME_SOURCE_REFERENCE",
        "output_epoch_count": output_count,
        "matched_epoch_count": matched,
        "unmatched_epoch_count": output_count - matched,
        "coverage": matched / output_count,
        "metrics": metrics,
        "continuity": {
            **dict(adapter),
            "matched_time_start_seconds": float(error_times[0]),
            "matched_time_end_seconds": float(error_times[-1]),
            "matched_strictly_chronological": True,
        },
        "native_runtime_seconds": native_runtime_seconds,
        "offline_evaluator_runtime_seconds": float(evaluator_result["runtime_seconds"]),
        "nis": dict(nis),
        "exact_evaluator_crosscheck_absolute_differences": crosschecks,
        "exact_evaluator_summary": exact,
    }


def _trace_result_row(result: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "method_id": result["method_id"],
        "status": result["status"],
        "output_epoch_count": result["output_epoch_count"],
        "matched_epoch_count": result["matched_epoch_count"],
        "unmatched_epoch_count": result["unmatched_epoch_count"],
        "coverage": result["coverage"],
        "native_runtime_seconds": result["native_runtime_seconds"],
        "offline_evaluator_runtime_seconds": result["offline_evaluator_runtime_seconds"],
        "nis_row_count": result["nis"]["row_count"],
        "nis_degrees_of_freedom": result["nis"]["degrees_of_freedom"],
        "nis_mean": result["nis"]["nis"]["mae"],
        "normalized_nis_mean": result["nis"]["normalized_nis"]["mae"],
    }
    for component, distribution in result["metrics"].items():
        for statistic, value in distribution.items():
            row[f"{component}_{statistic}"] = value
    return row


def _trace_report(results: Mapping[str, Mapping[str, Any]], overall: Mapping[str, Any]) -> str:
    lines = [
        "# EXT05A C00 post-native evaluation",
        "",
        f"Terminal status: `{overall['terminal_status']}`.",
        "",
        "The reference is the hash-locked same-source Fixposition trace and is not independent ground truth. "
        "It was opened only after the native freeze and direct geometric audit passed.",
        "",
        "| Method | H RMSE m | 3D RMSE m | Roll RMSE deg | Pitch RMSE deg | Yaw RMSE deg | Coverage | Native s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id in (METHOD_IEKF, METHOD_SINGLE):
        result = results[method_id]
        metrics = result["metrics"]
        lines.append(
            f"| {method_id} | {metrics['horizontal_m']['rmse']:.6f} | "
            f"{metrics['position_3d_m']['rmse']:.6f} | {metrics['roll_deg']['rmse']:.6f} | "
            f"{metrics['pitch_deg']['rmse']:.6f} | {metrics['yaw_deg']['rmse']:.6f} | "
            f"{result['coverage']:.9f} | {result['native_runtime_seconds']:.6f} |"
        )
    lines.extend([
        "",
        f"MEKF appendix baseline: `{MEKF_STATUS}` (human-waived; no synthetic or repaired MEKF result).",
        "",
        "No time, sign, frame, alignment, constant-offset, smoothing, output correction, or error-based epoch deletion was used.",
        "",
    ])
    return "\n".join(lines)


def _validate_trace_evaluation_freeze(paths: Phase5Paths) -> dict[str, Any]:
    evaluation_root = paths.c00_root / TRACE_EVALUATION_RELATIVE
    freeze_path = evaluation_root / "EXT05A_C00_TRACE_EVALUATION_FREEZE.json"
    if not freeze_path.is_file():
        raise Phase5RunnerError("trace evaluation freeze is absent")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if (
        freeze.get("terminal_status") != PASS_C00
        or freeze.get("trace_used_online") is not False
        or freeze.get("exact_evaluator_sha256") != EXACT_EVALUATOR_SHA256
    ):
        raise Phase5RunnerError("trace evaluation freeze contract drifted")
    files = freeze.get("files")
    if not isinstance(files, dict) or not files:
        raise Phase5RunnerError("trace evaluation freeze file set is absent")
    for relative_text, evidence in files.items():
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise Phase5RunnerError("trace evaluation freeze contains an unsafe path")
        path = evaluation_root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != int(evidence.get("size_bytes", -1))
            or sha256_file(path) != evidence.get("sha256")
        ):
            raise Phase5RunnerError(f"trace evaluation freeze payload drifted: {relative_text}")
    report = paths.report_root / "EXT05A_C00_VALIDITY_REPORT.md"
    report_evidence = freeze.get("report", {})
    if (
        not report.is_file()
        or report.is_symlink()
        or report.stat().st_size != int(report_evidence.get("size_bytes", -1))
        or sha256_file(report) != report_evidence.get("sha256")
    ):
        raise Phase5RunnerError("trace evaluation frozen report drifted")
    _validate_native_freeze(paths.c00_root)
    if sha256_file(paths.c00_root / NATIVE_FREEZE_NAME) != freeze.get("native_freeze_sha256"):
        raise Phase5RunnerError("trace evaluation no longer binds the native freeze")
    summary_path = evaluation_root / "EXT05A_C00_TRACE_EVALUATION_SUMMARY.json"
    if summary_path.relative_to(evaluation_root).as_posix() not in files:
        raise Phase5RunnerError("trace evaluation summary is outside the frozen payload set")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def run_trace_evaluation(
    paths: Phase5Paths,
    *,
    exact_evaluator: Path,
    resume: bool = False,
) -> dict[str, Any]:
    """Run only the authorized same-source trace evaluation after native freeze."""

    evaluator = Path(exact_evaluator).resolve(strict=True)
    evaluator_hash = sha256_file(evaluator)
    if evaluator_hash != EXACT_EVALUATOR_SHA256:
        raise Phase5RunnerError("exact evaluator SHA256 does not match aa049248")
    evaluator_contract_hash = sha256_file(FINAL_EVALUATOR_CONTRACT_PATH)
    contract = _mapping(FINAL_EVALUATOR_CONTRACT_PATH)
    if (
        contract.get("source_identity", {}).get("evaluator", {}).get("sha256")
        != EXACT_EVALUATOR_SHA256
        or contract.get("evaluator_contract", {}).get("evaluator_sha256")
        != EXACT_EVALUATOR_SHA256
    ):
        raise Phase5RunnerError("frozen evaluator contract does not bind exact evaluator")
    native_freeze = _validate_native_freeze(paths.c00_root)
    native_freeze_sha256 = sha256_file(paths.c00_root / NATIVE_FREEZE_NAME)
    geometric_summary_path = (
        paths.c00_root / "POST_NATIVE_GEOMETRIC_AUDIT/EXT05A_C00_GEOMETRIC_YAW_AUDIT.json"
    )
    if not geometric_summary_path.is_file():
        raise Phase5RunnerError("passing post-native geometric audit is absent")
    geometric_summary = json.loads(geometric_summary_path.read_text(encoding="utf-8"))
    if (
        geometric_summary.get("terminal_status") != PASS_C00
        or geometric_summary.get("thresholds_pass") is not True
        or geometric_summary.get("native_files_unchanged_after_audit") is not True
        or geometric_summary.get("native_freeze_sha256") != native_freeze_sha256
        or geometric_summary.get("trace_open_count") != 0
        or geometric_summary.get("trace_used") is not False
    ):
        raise Phase5RunnerError("post-native geometric audit is not a PASS gate")
    evaluation_root = paths.c00_root / TRACE_EVALUATION_RELATIVE
    evaluation_freeze_path = evaluation_root / "EXT05A_C00_TRACE_EVALUATION_FREEZE.json"
    report_destination = paths.report_root / "EXT05A_C00_VALIDITY_REPORT.md"
    if evaluation_root.exists():
        if resume and evaluation_freeze_path.is_file():
            return _validate_trace_evaluation_freeze(paths)
        raise Phase5RunnerError("trace evaluation output root already exists")
    if report_destination.exists():
        raise Phase5RunnerError("EXT05A C00 report destination already exists")

    evaluation_source_snapshot = _source_snapshot()
    native_summary = json.loads(
        (paths.c00_root / NATIVE_SUMMARY_NAME).read_text(encoding="utf-8")
    )
    provider = native_summary["provider"]
    native_runtime: dict[str, float] = {}
    with (paths.c00_root / RUNTIME_NAME).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["run_variant"] == "WORKERS_16":
                native_runtime[row["method_id"]] = float(row["runtime_seconds"])
    required_runtime = {METHOD_IEKF, METHOD_SINGLE}
    if set(native_runtime) != required_runtime:
        raise Phase5RunnerError("native workers16 runtime rows are incomplete")

    with tempfile.TemporaryDirectory(prefix="legsa_ext05_trace_eval_") as temporary:
        temporary_root = Path(temporary)
        method_specs = {
            METHOD_IEKF: (IEKF_NAV_NAME, IEKF_NIS_NAME),
            METHOD_SINGLE: (SINGLE_NAV_NAME, SINGLE_NIS_NAME),
        }
        adapters: dict[str, dict[str, Any]] = {}
        nis: dict[str, dict[str, Any]] = {}
        method_roots: dict[str, Path] = {}
        for method_id, (nav_name, nis_name) in method_specs.items():
            method_root = temporary_root / method_id
            method_root.mkdir(parents=True)
            method_roots[method_id] = method_root
            adapters[method_id] = _materialize_exact_evaluator_nav(
                paths.c00_root / nav_name,
                method_root / "EXACT_EVALUATOR_INPUT.nav",
                origin_ecef_m=provider["position"]["fixed_ned_origin_ecef_m"],
                ecef_to_ned=provider["position"]["fixed_ecef_to_ned"],
            )
            nis[method_id] = _nis_distribution(paths.c00_root / nis_name)

        # This is the first authorized trace open: byte/hash verification after
        # both native and geometric freezes, never solver input or tuning.
        trace_evidence = verify_hash_locked_file(
            paths.trace, raw_root=paths.raw_root, hash_lock=paths.by2_hash_lock
        )
        if trace_evidence["sha256"] != FROZEN_TRACE_SHA256:
            raise Phase5RunnerError("same-source trace differs from frozen evaluator contract")

        evaluator_results: dict[str, dict[str, Any]] = {}
        results: dict[str, dict[str, Any]] = {}
        for method_id in (METHOD_IEKF, METHOD_SINGLE):
            evaluator_results[method_id] = _run_verified_exact_evaluator(
                evaluator=evaluator,
                trace=paths.trace,
                nav=method_roots[method_id] / "EXACT_EVALUATOR_INPUT.nav",
                method_root=method_roots[method_id],
            )
            results[method_id] = _supplement_exact_metrics(
                method_id=method_id,
                evaluator_result=evaluator_results[method_id],
                adapter=adapters[method_id],
                nis=nis[method_id],
                native_runtime_seconds=native_runtime[method_id],
            )

        if sha256_file(evaluator) != evaluator_hash:
            raise Phase5RunnerError("exact evaluator bytes changed during evaluation")

        _validate_native_freeze(paths.c00_root)
        _revalidate_source_snapshot(evaluation_source_snapshot)
        trace_open_count = 1 + sum(
            value["trace_open_count"] for value in evaluator_results.values()
        )
        overall = {
            "schema_version": "horizontal_literature.ext05.c00.trace_evaluation.v1",
            "terminal_status": PASS_C00,
            "methods": results,
            METHOD_MEKF: {"status": MEKF_STATUS, "human_waiver": True},
            "exact_evaluator": {
                "sha256": evaluator_hash,
                "archive_member": "KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py",
                "path": str(evaluator),
                "contract_path": str(FINAL_EVALUATOR_CONTRACT_PATH),
                "contract_sha256": evaluator_contract_hash,
                "hash_verification_open_count": 3,
                "std_input": None,
                "std_omission_reason": "LEFT_INVARIANT_BODY_TANGENT_COVARIANCE_IS_NOT_EXACT_EULER_STD",
                "per_method_execution": {
                    method_id: {
                        key: evaluator_results[method_id][key]
                        for key in (
                            "command", "returncode", "runtime_seconds",
                            "trace_open_count", "nav_open_count", "evaluator_open_count",
                            "strace_sha256", "summary_sha256", "error_series_sha256",
                        )
                    }
                    for method_id in evaluator_results
                },
            },
            "trace": {
                **trace_evidence,
                "role": "SAME_SOURCE_POST_NATIVE_EVALUATION_REFERENCE_NOT_INDEPENDENT_GROUND_TRUTH",
                "post_native_open_count": trace_open_count,
                "hash_verification_open_count": 1,
                "exact_evaluator_open_count_by_method": {
                    method_id: evaluator_results[method_id]["trace_open_count"]
                    for method_id in evaluator_results
                },
            },
            "contract": {
                "base_time_unix_seconds": BASE_TIME,
                "window_seconds": [WINDOW_START, WINDOW_END],
                "yaw": "unwrap_trace_ENU_then_interpolate_then_wrap360(90-yaw)",
                "time_search": False,
                "frame_search": False,
                "alignment": False,
                "constant_offset_correction": False,
                "error_based_epoch_deletion": False,
                "output_only_correction": False,
            },
            "native_freeze_sha256": native_freeze_sha256,
            "native_file_count_revalidated_before_and_after": len(native_freeze["files"]),
            "native_files_unchanged": True,
            "evaluation_code_snapshot": evaluation_source_snapshot,
            "evaluation_source_snapshot_revalidation_count": 2,
            "thread_environment": {
                name: os.environ[name]
                for name in (
                    "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                )
            },
        }
        _write_json(temporary_root / "EXT05A_C00_TRACE_EVALUATION_SUMMARY.json", overall)
        result_rows = [_trace_result_row(results[method]) for method in (METHOD_IEKF, METHOD_SINGLE)]
        result_fields = list(result_rows[0])
        _write_csv(
            temporary_root / "EXT05A_C00_TRACE_METHOD_RESULTS.csv",
            result_fields,
            result_rows,
        )
        ledger_rows = [
            {
                "read_order": 1,
                "role": "native_freeze_revalidation",
                "path_alias": f"<EXT05_C00>/{NATIVE_FREEZE_NAME}",
                "sha256": overall["native_freeze_sha256"],
                "open_count": 3,
            },
            {
                "read_order": 2,
                "role": "exact_frozen_evaluator",
                "path_alias": "<SELECTED_ARCHIVE>/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py",
                "sha256": evaluator_hash,
                "open_count": 3 + sum(
                    evaluator_results[method]["evaluator_open_count"]
                    for method in evaluator_results
                ),
            },
            {
                "read_order": 3,
                "role": "same_source_post_native_reference",
                "path_alias": f"<RAW_ROOT>/{trace_evidence['relative_path']}",
                "sha256": trace_evidence["sha256"],
                "open_count": trace_open_count,
            },
        ]
        _write_csv(
            temporary_root / "EXT05A_C00_TRACE_EVALUATION_READ_LEDGER.csv",
            ("read_order", "role", "path_alias", "sha256", "open_count"),
            ledger_rows,
        )
        report_text = _trace_report(results, overall)
        _write_text(temporary_root / "EXT05A_C00_VALIDITY_REPORT.md", report_text)

        evaluation_root.mkdir(parents=True, exist_ok=False)
        for source in sorted(temporary_root.rglob("*")):
            if source.is_file():
                _copy_exclusive(source, evaluation_root / source.relative_to(temporary_root))
        paths.report_root.mkdir(parents=True, exist_ok=True)
        _copy_exclusive(
            evaluation_root / "EXT05A_C00_VALIDITY_REPORT.md", report_destination
        )
        _validate_native_freeze(paths.c00_root)
        _revalidate_source_snapshot(evaluation_source_snapshot)
        if sha256_file(evaluator) != evaluator_hash:
            raise Phase5RunnerError("exact evaluator changed before evaluation freeze")
        evaluation_files = {
            path.relative_to(evaluation_root).as_posix(): {
                "sha256": sha256_file(path), "size_bytes": path.stat().st_size
            }
            for path in sorted(evaluation_root.rglob("*")) if path.is_file()
        }
        freeze = {
            "schema_version": "horizontal_literature.ext05.c00.trace_evaluation_freeze.v1",
            "terminal_status": PASS_C00,
            "files": evaluation_files,
            "report": {
                "path_alias": "<STAGE>/11_REPORT/EXT05A_C00_VALIDITY_REPORT.md",
                "sha256": sha256_file(report_destination),
                "size_bytes": report_destination.stat().st_size,
            },
            "native_freeze_sha256": overall["native_freeze_sha256"],
            "native_files_unchanged": True,
            "trace_used_online": False,
            "trace_post_native_open_count": trace_open_count,
            "exact_evaluator_sha256": evaluator_hash,
            "source_snapshot_revalidated_immediately_before_freeze": True,
            "evaluator_revalidated_immediately_before_freeze": True,
            "native_freeze_revalidated_immediately_before_freeze": True,
        }
        _write_json(evaluation_freeze_path, freeze)
        return overall
