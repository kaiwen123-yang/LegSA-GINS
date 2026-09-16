"""Sequence-scoped EXT05 adapter; native execution never opens reference trace.

The chronological loop is the frozen PHASE5 loop with explicit sequence time
and shared-parameter injection.  PHASE5 and the filter implementation remain
unmodified.  H-EXT-01's CLI admits only the two default BY2 identity runs.
"""
from __future__ import annotations

import csv
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

for _thread_variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_variable] = "1"

import numpy as np

from ..horizontal_literature.ext05_pavlasek import (
    METHOD_IEKF, METHOD_SINGLE, ExtendedPose, PavlasekIEKF,
    finite_filter_snapshot, rotation_to_rpy_ned_frd_deg,
)
from ..horizontal_literature.ext05_provider import (
    BASELINE_BODY_FRD_M, LEVER_IMU_TO_RECEIVER1_FRD_M,
    EXPECTED_POSITION_EPOCHS, EXPECTED_RAWX_EPOCHS, EXPECTED_IMU_SAMPLES,
    EXPECTED_GPS_WEEK, EXPECTED_LEAP_SECONDS,
    build_imu_only_provider, build_solution_position_provider,
    calibrate_static_imu, initial_attitude_from_gravity_and_baseline, sha256_file,
)
from ..horizontal_literature import phase5_runner as phase5
from ..horizontal_literature.phase5_runner import (
    NAV_FIELDS, INNOVATION_FIELDS, NIS_FIELDS, GEOMETRIC_AUDIT_FIELDS,
    Phase5RunnerError, _load_cache, _calibration_payload, _append_nav,
    _write_csv, _write_json, _aggregate_hash, _finite_csv_float,
    _geometric_audit_rows, _wrap180_degrees,
)
from ..horizontal_literature.shared_raw_backend import ecef_to_geodetic
from .parameters import (
    Ext05Parameters, load_parameters, require_implemented_gap_policy,
    scaled_frd_specific_force,
)


@dataclass(frozen=True)
class ExpectedCounts:
    position_epochs: int = EXPECTED_POSITION_EPOCHS
    rawx_epochs: int = EXPECTED_RAWX_EPOCHS
    imu_samples: int = EXPECTED_IMU_SAMPLES
    gps_week: int = EXPECTED_GPS_WEEK
    leap_seconds: int = EXPECTED_LEAP_SECONDS


def _nav_row(method_id: str, absolute_time: float, filter_: PavlasekIEKF, *, base_time: float) -> dict[str, Any]:
    row = phase5._nav_row(method_id, absolute_time, filter_)
    row["time_seconds"] = absolute_time - base_time
    return row


def _build_cache(paths: Any, root: Path, *, expected: ExpectedCounts, provenance: Mapping[str, Any]) -> dict[str, Any]:
    positions = build_solution_position_provider(
        paths.gnss1_raw, paths.gnss2_raw,
        raw_root=paths.raw_root, hash_lock=paths.hash_lock,
        expected_position_epochs=expected.position_epochs,
        expected_rawx_epochs=expected.rawx_epochs,
        expected_gps_week=expected.gps_week,
        expected_leap_seconds=expected.leap_seconds,
    )
    imu, imu_report, imu_hash = build_imu_only_provider(
        paths.go2_body, raw_root=paths.raw_root, hash_lock=paths.hash_lock,
        expected_imu_samples=expected.imu_samples,
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
    run_provenance = {
        **provenance,
        "raw_source_hashes": {**positions.source_hashes, "go2_body": imu_hash},
        "provider_hashes": array_hashes,
    }
    metadata = {
        **run_provenance,
        "run_provenance": run_provenance,
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


def _run_filter_sequence(
    cache_root_text: str, *, two_receiver: bool, output_root_text: str,
    base_time: float, parameters: Ext05Parameters
) -> dict[str, Any]:
    """One recursive sequence; this function alone owns its chronological loop."""

    require_implemented_gap_policy(parameters)
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
        gyro_psd=parameters.gyro_psd_rad2_s,
        accelerometer_psd=parameters.accel_psd_m2_s3,
        gravity_ned_mps2=[0.0, 0.0, float(calibration["local_gravity_mps2"])],
        two_receiver=two_receiver,
    )
    previous_imu_index = int(np.searchsorted(imu_times, initial_time, side="right") - 1)
    if previous_imu_index < 0:
        raise Phase5RunnerError("initial position precedes the Go2 IMU")
    gyro_bias = np.asarray(calibration["gyro_bias_frd_radps"], dtype=float)
    current_gyro = np.asarray(arrays["gyro"][previous_imu_index], dtype=float) - gyro_bias
    current_accel = scaled_frd_specific_force(
        np.asarray(arrays["accel"][previous_imu_index], dtype=float), parameters.accel_scale
    )
    imu_index = previous_imu_index + 1
    solution_index = initial_solution_index + 1
    state_time = initial_time
    nav_rows: list[dict[str, Any]] = []
    innovation_rows: list[dict[str, Any]] = []
    nis_rows: list[dict[str, Any]] = []
    _append_nav(nav_rows, _nav_row(method_id, state_time, filter_, base_time=base_time))
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
            current_accel = scaled_frd_specific_force(
                np.asarray(arrays["accel"][imu_index], dtype=float), parameters.accel_scale
            )
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
                    "time_seconds": state_time - base_time,
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
                    "time_seconds": state_time - base_time,
                    "nis": diagnostics.nis,
                    "degrees_of_freedom": 6 if two_receiver else 3,
                    "normalized_nis": diagnostics.nis / (6 if two_receiver else 3),
                })
                processed_solution_count += 1
        _append_nav(nav_rows, _nav_row(method_id, state_time, filter_, base_time=base_time))
    beyond_support = int(np.sum(solution_times > imu_times[-1]))
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
        **manifest.get("run_provenance", {}),
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


def materialize_exact_evaluator_nav(
    native_nav: Path,
    destination: Path,
    *,
    origin_ecef_m: Sequence[float],
    ecef_to_ned: Sequence[Sequence[float]],
    base_time: float,
    window: tuple[float, float],
) -> dict[str, Any]:
    """Adapt frozen local-NED NAV to the exact evaluator's 11-column LLA NAV."""

    window_start, window_end = window
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
                absolute = _finite_csv_float(row, "absolute_time_unix_seconds")
                if time_seconds != absolute - base_time:
                    raise Phase5RunnerError("native relative time disagrees with sequence base_time")
                if not window_start <= time_seconds <= window_end:
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
        "window_seconds": [window_start, window_end],
        "window_selection": "CLOSED_FIXED_NATIVE_TIME_NO_ERROR_SELECTION",
        "position_conversion": "fixed_NED_to_ECEF_to_WGS84_geodetic",
    }

def _source_snapshot(paths: Any, contract_path: Path) -> dict[str, str]:
    """Record maintained dependencies and this adapter without inspecting trace."""
    snapshot = phase5._source_snapshot()
    hashes = {relative: row["sha256"] for relative, row in snapshot["files"].items()}
    for path in (
        Path(__file__), Path(__file__).with_name("parameters.py"),
        Path(__file__).with_name("__init__.py"),
        Path(__file__).with_name("sequence_paths.py"),
        paths.code_root / "scripts/paper_rebuild/hext_native.py",
        contract_path,
        paths.code_root / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml",
        paths.code_root / "configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml",
    ):
        hashes[path.relative_to(paths.code_root).as_posix()] = sha256_file(path)
    return hashes


def _geometric_audit(method_root: Path, *, initial_time: float, base_time: float) -> dict[str, Any]:
    """Frozen PHASE5 diagnostic; its status never selects parameters or output."""
    with (method_root / "INNOVATION.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = _geometric_audit_rows(list(csv.DictReader(handle)), initial_time=initial_time)
    for row in rows:
        row["time_seconds"] = row["absolute_time_unix_seconds"] - base_time
    with (method_root / "NAV.csv").open("r", encoding="utf-8", newline="") as handle:
        nav = list(csv.DictReader(handle))
    times = np.asarray([_finite_csv_float(row, "absolute_time_unix_seconds") for row in nav])
    yaw = np.asarray([_finite_csv_float(row, "yaw_ned_deg") for row in nav])
    if len(nav) < 2 or np.any(np.diff(times) <= 0.0):
        raise Phase5RunnerError("frozen IEKF NAV is not strictly chronological")
    differences = np.asarray([
        _wrap180_degrees(float(later - earlier)) for earlier, later in zip(yaw, yaw[1:])
    ])
    maximum = float(np.max(np.abs(differences)))
    continuity = {
        "nav_row_count": len(nav),
        "maximum_adjacent_wrapsafe_yaw_step_deg": maximum,
        "adjacent_wrapsafe_yaw_step_ge_90_count": int(np.sum(np.abs(differences) >= 90.0)),
        "no_180_degree_representation_discontinuity": bool(maximum < 90.0),
    }
    absolute = np.asarray([float(row["absolute_yaw_difference_deg"]) for row in rows])
    direction = np.asarray([float(row["measured_estimated_direction_angle_deg"]) for row in rows])
    median = float(np.median(absolute))
    p95 = float(np.percentile(absolute, 95.0))
    thresholds_pass = median <= 10.0 and p95 <= 30.0
    implementation_consistent = thresholds_pass and bool(continuity["no_180_degree_representation_discontinuity"])
    _write_csv(method_root / "GEOMETRIC_AUDIT.csv", GEOMETRIC_AUDIT_FIELDS, rows)
    return {
        "terminal_status": phase5.PASS_C00 if implementation_consistent else "BLOCKED_EXT05_FRAME_SIGN_STATE_UPDATE_GEOMETRIC_AUDIT",
        "audit_role": "POST_NATIVE_IMPLEMENTATION_AUDIT_NOT_REFERENCE_EVALUATION",
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
        "result_is_status_only": True,
    }


def run_native_sequence(
    sequence: Any,
    output_root: Path,
    *,
    phase5_contract_path: Path,
    code_commit: str,
    expected: ExpectedCounts | Mapping[str, int] | None = None,
    workers: int = 2,
    sensor_model_path: Path | None = None,
    variant_enabled: bool = False,
    methods: tuple[str, ...] = (METHOD_IEKF, METHOD_SINGLE),
) -> dict[str, Any]:
    """Execute only H-EXT-01's two BY2 literature identity sequences, once each.

    Future sequence/variant execution needs separate H-EXT-02 authorization;
    parameterized helpers above are available for that later adapter review.
    Neither the reference path nor its payload is accessed here.
    """
    if sequence.sequence_id != "BY2" or variant_enabled:
        raise PermissionError("H-EXT-01 authorizes only default BY2 native identity runs")
    if set(methods) != {METHOD_IEKF, METHOD_SINGLE} or len(methods) != 2:
        raise ValueError("H-EXT-01 requires exactly EXT05A and EXT05C")
    if not 1 <= workers <= 20:
        raise ValueError("workers must be in [1,20]")
    output_root = Path(output_root)
    output_root.resolve().relative_to(sequence.hext_scratch.resolve())
    parameters = load_parameters(phase5_contract_path, variant_enabled=variant_enabled, sensor_model_path=sensor_model_path)
    require_implemented_gap_policy(parameters)
    counts = ExpectedCounts(**dict(expected)) if isinstance(expected, Mapping) else expected or ExpectedCounts()
    provider_contract = parameters.phase5_parameter_blocks["solution_provider"]
    if counts.position_epochs != int(provider_contract["expected_common_epoch_count"]) or counts.rawx_epochs != int(provider_contract["expected_rawx_epoch_count_per_receiver"]):
        raise ValueError("BY2 expected counts disagree with the frozen PHASE5 contract")
    snapshot = _source_snapshot(sequence, phase5_contract_path)
    lock_digest = sha256_file(sequence.hash_lock)
    if lock_digest != sequence.hash_lock_sha256:
        raise ValueError("raw hash-lock file disagrees with frozen sequence identity")
    provenance = {
        "data_mode": "real_by2_raw_identity_only",
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "code_commit": code_commit,
        "config_hash": sha256_file(phase5_contract_path),
        "source_hashes": snapshot,
        "raw_hash_lock_sha256": lock_digest,
        "hash_lock_note": sequence.hash_lock_note,
        "trace_open_count": 0,
        "evaluator_invocation_count": 0,
    }
    output_root.mkdir(parents=True, exist_ok=False)
    cache_root = output_root / "PROVIDER_CACHE"
    cache_manifest = _build_cache(sequence, cache_root, expected=counts, provenance=provenance)
    run_provenance = {
        **provenance,
        "raw_source_hashes": cache_manifest["source_hashes"],
        "provider_hashes": cache_manifest["array_hashes"],
    }
    _write_json(output_root / "RUN_INPUTS.json", {
        **run_provenance,
        "sequence_id": sequence.sequence_id,
        "base_time": sequence.base_time,
        "window": list(sequence.window),
        "expected": asdict(counts),
        "parameters": asdict(parameters),
        "native_invocation_budget": 2,
        "reference_access_audit": "EXTERNAL_STRACE_RECEIPT_REQUIRED",
    })
    results: dict[str, Any] = {}
    with ProcessPoolExecutor(max_workers=min(workers, 2)) as executor:
        pending = {
            method: executor.submit(
                _run_filter_sequence, str(cache_root),
                two_receiver=method == METHOD_IEKF,
                output_root_text=str(output_root / method),
                base_time=sequence.base_time,
                parameters=parameters,
            ) for method in methods
        }
        for method, future in pending.items():
            results[method] = future.result()
    native_hashes = {
        (Path(item["output_root"]) / filename).relative_to(output_root).as_posix(): digest
        for item in results.values() for filename, digest in item["file_hashes"].items()
    }
    _write_json(output_root / "NATIVE_FREEZE.json", {
        **run_provenance, "files": native_hashes, "native_invocation_count": len(methods),
        "recursive_epoch_parallelism": False, "workers": min(workers, 2),
    })
    adapters: dict[str, Any] = {}
    for method, item in results.items():
        method_root = Path(item["output_root"])
        adapters[method] = materialize_exact_evaluator_nav(
            method_root / "NAV.csv", method_root / "EXACT_EVALUATOR_INPUT.nav",
            origin_ecef_m=cache_manifest["origin_ecef_m"],
            ecef_to_ned=cache_manifest["ecef_to_ned"],
            base_time=sequence.base_time, window=sequence.window,
        )
    try:
        dual = results[METHOD_IEKF]
        geometric = _geometric_audit(
            Path(dual["output_root"]), initial_time=dual["summary"]["initial_time_unix_seconds"],
            base_time=sequence.base_time,
        )
    except (OSError, ValueError, Phase5RunnerError) as exc:
        geometric = {"terminal_status": "UNAVAILABLE", "error": str(exc), "result_is_status_only": True}
    _write_json(output_root / "GEOMETRIC_AUDIT.json", {**run_provenance, **geometric})
    if any(sha256_file(output_root / name) != digest for name, digest in native_hashes.items()):
        raise ValueError("native files changed after freeze")
    if _source_snapshot(sequence, phase5_contract_path) != snapshot:
        raise ValueError("native source snapshot changed")
    summary = {
        **run_provenance,
        "terminal_status": "NATIVE_COMPLETED_PENDING_EXTERNAL_BY2_BYTE_IDENTITY_GATE",
        "sequence_id": sequence.sequence_id,
        "base_time": sequence.base_time,
        "window": list(sequence.window),
        "parameters": asdict(parameters),
        "provider": cache_manifest,
        "methods": results,
        "adapters": adapters,
        "geometric_audit": geometric,
        "native_invocation_count": len(methods),
        "variant_enabled": variant_enabled,
        "performance_table_admission": False,
    }
    _write_json(output_root / "NATIVE_SUMMARY.json", summary)
    return summary
