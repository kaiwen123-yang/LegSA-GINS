"""N4G BY2 filter-core diagnostic trial adapters.

中文说明：本模块只构造 event-normalized diagnostic trial 输入；不使用 trace 对齐
solver，不读取 final_v23 output，不实现 raw Doppler / Go2 prior / weighting / FGO。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.datasets.by2.dual_antenna_heading_convention import (
    apply_transverse_heading_offset,
    heading_offset_deg_for_mode,
)
from legsa_gins.datasets.by2.unitree_imu_semantics import quaternion_wxyz_to_rpy


GRAVITY_MPS2 = 9.80665
IMU_PROPAGATION_MODES = [
    "gyro_only_zero_dvel",
    "quaternion_gravity_compensated",
    "raw_accel_direct_deprecated_diagnostic",
]

IMU_INCREMENT_HEADER = [
    "timestamp",
    "raw_time",
    "algo_time_sec",
    "tow",
    "dt",
    "dtheta_x",
    "dtheta_y",
    "dtheta_z",
    "dvel_x",
    "dvel_y",
    "dvel_z",
    "frame",
    "source_role",
    "imu_propagation_mode",
    "imu_accel_used_for_dvel",
    "accel_contains_gravity",
    "frame_transform_applied_once",
    "deprecated",
]

RECEIVER_TRIAL_HEADER = [
    "timestamp",
    "raw_time",
    "algo_time_sec",
    "tow",
    "lat_deg",
    "lon_deg",
    "height_m",
    "vn_mps",
    "ve_mps",
    "vd_mps",
    "yaw_deg",
    "baseline_heading_deg",
    "body_heading_candidate_deg",
    "heading_offset_mode",
    "heading_offset_deg",
    "heading_mounting_diagnostic_only",
    "pos_std_m",
    "vel_std_mps",
    "yaw_std_deg",
    "has_position",
    "has_velocity",
    "has_heading",
    "source_name",
]


def _as_float(value: Any, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return default
    parsed = float(text)
    if math.isnan(parsed):
        return default
    return parsed


def _as_bool(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _quat_rotate(q: list[float], v: tuple[float, float, float]) -> tuple[float, float, float]:
    w, x, y, z = q
    vx, vy, vz = v
    # q * v * conj(q), written out to avoid external dependencies.
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def _gravity_compensated_dvel(row: dict[str, str], dt: float) -> tuple[float, float, float]:
    acc_frd = (
        _as_float(row.get("acc_x"), default=0.0) or 0.0,
        -(_as_float(row.get("acc_y"), default=0.0) or 0.0),
        -(_as_float(row.get("acc_z"), default=0.0) or 0.0),
    )
    quat = [
        _as_float(row.get("quat_w", row.get("quat_0")), default=1.0) or 1.0,
        _as_float(row.get("quat_x", row.get("quat_1")), default=0.0) or 0.0,
        -(_as_float(row.get("quat_y", row.get("quat_2")), default=0.0) or 0.0),
        -(_as_float(row.get("quat_z", row.get("quat_3")), default=0.0) or 0.0),
    ]
    norm = math.sqrt(sum(value * value for value in quat))
    quat = [value / norm for value in quat] if norm > 0.0 else [1.0, 0.0, 0.0, 0.0]
    _ = quaternion_wxyz_to_rpy(quat)
    nav_acc = _quat_rotate(quat, acc_frd)
    nav_acc = (nav_acc[0], nav_acc[1], nav_acc[2] - GRAVITY_MPS2)
    return (nav_acc[0] * dt, nav_acc[1] * dt, nav_acc[2] * dt)


def convert_go2_body_state_to_imu_increments(
    body_state_csv: str | Path,
    output_csv: str | Path,
    *,
    max_rows: int | None = None,
    imu_propagation_mode: str = "gyro_only_zero_dvel",
) -> dict[str, Any]:
    """Convert normalized BY2 Go2 body-state rows into diagnostic IMU increments."""

    if imu_propagation_mode not in IMU_PROPAGATION_MODES:
        raise ValueError(f"Unsupported imu_propagation_mode: {imu_propagation_mode}")
    input_path = Path(body_state_csv)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped_nonpositive_dt = 0
    skipped_missing = 0
    previous_algo_time: float | None = None

    with input_path.open("r", encoding="utf-8", newline="") as source, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=IMU_INCREMENT_HEADER)
        writer.writeheader()
        for index, row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            algo_time = _as_float(row.get("algo_time_sec"), default=_as_float(row.get("timestamp")))
            raw_time = _as_float(row.get("raw_time"), default=_as_float(row.get("timestamp")))
            gyro_x = _as_float(row.get("gyro_x"))
            gyro_y = _as_float(row.get("gyro_y"))
            gyro_z = _as_float(row.get("gyro_z"))
            if None in {algo_time, gyro_x, gyro_y, gyro_z}:
                skipped_missing += 1
                continue
            if previous_algo_time is None:
                previous_algo_time = algo_time
                continue
            dt = algo_time - previous_algo_time
            previous_algo_time = algo_time
            if dt <= 0.0:
                skipped_nonpositive_dt += 1
                continue
            dtheta = (gyro_x * dt, -gyro_y * dt, -gyro_z * dt)
            if imu_propagation_mode == "gyro_only_zero_dvel":
                dvel = (0.0, 0.0, 0.0)
                accel_used = False
                deprecated = False
            elif imu_propagation_mode == "quaternion_gravity_compensated":
                dvel = _gravity_compensated_dvel(row, dt)
                accel_used = True
                deprecated = False
            else:
                dvel = (
                    (_as_float(row.get("acc_x"), default=0.0) or 0.0) * dt,
                    -(_as_float(row.get("acc_y"), default=0.0) or 0.0) * dt,
                    -(_as_float(row.get("acc_z"), default=0.0) or 0.0) * dt,
                )
                accel_used = True
                deprecated = True
            writer.writerow(
                {
                    "timestamp": f"{algo_time:.9f}",
                    "raw_time": _csv_value(raw_time),
                    "algo_time_sec": f"{algo_time:.9f}",
                    "tow": f"{algo_time:.9f}",
                    "dt": f"{dt:.9f}",
                    "dtheta_x": f"{dtheta[0]:.12g}",
                    "dtheta_y": f"{dtheta[1]:.12g}",
                    "dtheta_z": f"{dtheta[2]:.12g}",
                    "dvel_x": f"{dvel[0]:.12g}",
                    "dvel_y": f"{dvel[1]:.12g}",
                    "dvel_z": f"{dvel[2]:.12g}",
                    "frame": "IMU_FRD_COMPATIBLE",
                    "source_role": "go2_body_state_diagnostic_imu_increment",
                    "imu_propagation_mode": imu_propagation_mode,
                    "imu_accel_used_for_dvel": accel_used,
                    "accel_contains_gravity": True,
                    "frame_transform_applied_once": True,
                    "deprecated": deprecated,
                }
            )
            written += 1

    evidence = {
        "gyro_only_zero_dvel": "diagnostic_zero_dvel_candidate",
        "quaternion_gravity_compensated": "diagnostic_gravity_compensated_candidate",
        "raw_accel_direct_deprecated_diagnostic": "deprecated_raw_accel_direct_diagnostic",
    }[imu_propagation_mode]
    return {
        "input": str(input_path),
        "output": str(output_path),
        "rows_written": written,
        "skipped_missing": skipped_missing,
        "skipped_nonpositive_dt": skipped_nonpositive_dt,
        "imu_propagation_mode": imu_propagation_mode,
        "imu_accel_used_for_dvel": imu_propagation_mode != "gyro_only_zero_dvel",
        "deprecated": imu_propagation_mode == "raw_accel_direct_deprecated_diagnostic",
        "source_frame": "FLU",
        "output_frame": "IMU_FRD_COMPATIBLE",
        "frame_transform_applied_once": True,
        "accel_contains_gravity": True,
        "receiver_imu_as_body_imu": False,
        "trace_solver_input": False,
        "evidence_status": evidence,
    }


def make_receiver_measurement_trial_csv(
    gnss_status_standard_csv: str | Path,
    output_csv: str | Path,
    *,
    source_name: str,
    heading_offset_mode: str = "no_offset",
) -> dict[str, Any]:
    input_path = Path(gnss_status_standard_csv)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    offset_deg = heading_offset_deg_for_mode(heading_offset_mode)
    written = 0
    position_rows = 0
    heading_rows = 0
    with input_path.open("r", encoding="utf-8", newline="") as source, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=RECEIVER_TRIAL_HEADER)
        writer.writeheader()
        for row in reader:
            raw_time = _as_float(row.get("raw_time"), default=_as_float(row.get("time_unix")))
            algo_time = _as_float(row.get("algo_time_sec"), default=_as_float(row.get("tow")))
            lat = _as_float(row.get("lat_deg"))
            lon = _as_float(row.get("lon_deg"))
            height = _as_float(row.get("height_m"))
            has_position = _as_bool(row.get("has_position")) and None not in {lat, lon, height}
            pos_std = _as_float(row.get("pos_acc_h_m"), default=10.0) or 10.0
            baseline_heading = _as_float(row.get("heading_deg"))
            has_heading = _as_bool(row.get("heading_valid")) and baseline_heading is not None
            body_heading = (
                apply_transverse_heading_offset(baseline_heading, offset_deg)
                if has_heading and baseline_heading is not None
                else 0.0
            )
            rel_acc_n = _as_float(row.get("rel_acc_n_m"))
            rel_acc_e = _as_float(row.get("rel_acc_e_m"))
            yaw_std = 5.0
            if rel_acc_n is not None and rel_acc_e is not None:
                yaw_std = max(1.0, math.degrees(math.hypot(rel_acc_n, rel_acc_e)))
            position_rows += 1 if has_position else 0
            heading_rows += 1 if has_heading else 0
            writer.writerow(
                {
                    "timestamp": _csv_value(raw_time),
                    "raw_time": _csv_value(raw_time),
                    "algo_time_sec": _csv_value(algo_time),
                    "tow": _csv_value(algo_time),
                    "lat_deg": _csv_value(lat),
                    "lon_deg": _csv_value(lon),
                    "height_m": _csv_value(height),
                    "vn_mps": "0.0",
                    "ve_mps": "0.0",
                    "vd_mps": "0.0",
                    "yaw_deg": _csv_value(body_heading),
                    "baseline_heading_deg": _csv_value(baseline_heading),
                    "body_heading_candidate_deg": _csv_value(body_heading),
                    "heading_offset_mode": heading_offset_mode,
                    "heading_offset_deg": _csv_value(offset_deg),
                    "heading_mounting_diagnostic_only": True,
                    "pos_std_m": _csv_value(pos_std),
                    "vel_std_mps": "10.0",
                    "yaw_std_deg": _csv_value(yaw_std),
                    "has_position": has_position,
                    "has_velocity": False,
                    "has_heading": has_heading,
                    "source_name": source_name,
                }
            )
            written += 1
    return {
        "input": str(input_path),
        "output": str(output_path),
        "source_name": source_name,
        "rows_written": written,
        "position_rows": position_rows,
        "heading_rows": heading_rows,
        "heading_offset_mode": heading_offset_mode,
        "heading_offset_deg": offset_deg,
        "heading_mounting_diagnostic_only": True,
        "has_velocity": False,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
    }


def count_receiver_position_rows(path: str | Path) -> int:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for row in csv.DictReader(handle) if _as_bool(row.get("has_position")))


def select_receiver_status_csv(inputs_dir: str | Path) -> tuple[Path, str]:
    inputs = Path(inputs_dir)
    gnss2 = inputs / "BY2_GNSS2_STATUS_STANDARD.csv"
    if gnss2.exists() and count_receiver_position_rows(gnss2) > 0:
        return gnss2, "gnss2"
    return inputs / "BY2_GNSS1_STATUS_STANDARD.csv", "gnss1"


def write_toy_standardized_inputs(output_dir: str | Path, *, row_count: int = 360) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    start = 1_700_000_000.0
    dt = 0.05
    lat0 = 30.0
    lon0 = 120.0
    height0 = 15.0

    gnss_header = [
        "time_unix",
        "gps_week",
        "tow",
        "lat_deg",
        "lon_deg",
        "height_m",
        "pos_acc_h_m",
        "pos_acc_v_m",
        "pos_valid",
        "fix_ok",
        "fix_type",
        "has_position",
        "rel_pos_n_m",
        "rel_pos_e_m",
        "rel_pos_d_m",
        "rel_acc_n_m",
        "rel_acc_e_m",
        "rel_acc_d_m",
        "rel_valid",
        "ant_valid",
        "heading_deg",
        "heading_valid",
        "source_name",
        "source_role",
    ]

    def write_gnss(path: Path, source_name: str, has_position: bool) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=gnss_header)
            writer.writeheader()
            for index in range(row_count):
                moving = index >= 24
                timestamp = start + index * dt
                move = max(0, index - 24)
                writer.writerow(
                    {
                        "time_unix": f"{timestamp:.9f}",
                        "gps_week": 2409,
                        "tow": f"{1000.0 + index * dt:.9f}",
                        "lat_deg": f"{lat0 + move * 1.0e-7:.12f}",
                        "lon_deg": f"{lon0 + move * 1.2e-7:.12f}",
                        "height_m": f"{height0 + move * 0.001:.6f}",
                        "pos_acc_h_m": "1.5",
                        "pos_acc_v_m": "2.0",
                        "pos_valid": has_position,
                        "fix_ok": has_position,
                        "fix_type": "3d",
                        "has_position": has_position,
                        "rel_pos_n_m": "1.0",
                        "rel_pos_e_m": "0.0",
                        "rel_pos_d_m": "0.0",
                        "rel_acc_n_m": "0.02",
                        "rel_acc_e_m": "0.02",
                        "rel_acc_d_m": "0.02",
                        "rel_valid": moving,
                        "ant_valid": moving,
                        "heading_deg": "0.0",
                        "heading_valid": moving,
                        "source_name": source_name,
                        "source_role": "receiver_native_gnss_status",
                    }
                )

    write_gnss(out / "BY2_GNSS1_STATUS_STANDARD.csv", "gnss1", True)
    write_gnss(out / "BY2_GNSS2_STATUS_STANDARD.csv", "gnss2", True)

    body_header = [
        "timestamp",
        "quat_w",
        "quat_x",
        "quat_y",
        "quat_z",
        "quat_0",
        "quat_1",
        "quat_2",
        "quat_3",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "acc_x",
        "acc_y",
        "acc_z",
        "roll_rad",
        "pitch_rad",
        "yaw_rad",
        "mode",
        "gait_type",
        "go2_velocity_0",
        "go2_velocity_1",
        "go2_velocity_2",
        "yaw_speed_radps",
        *[f"foot_force_{index}" for index in range(4)],
        *[f"foot_speed_body_{index}" for index in range(12)],
        "source_role",
        "body_frame",
        "accel_contains_gravity",
        "quaternion_order",
        "rpy_order",
    ]
    with (out / "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=body_header)
        writer.writeheader()
        for index in range(row_count):
            timestamp = start + index * dt
            kick = index == 10
            moving = index >= 20
            yaw_rate = 0.08 if moving else 0.0
            row = {
                "timestamp": f"{timestamp:.9f}",
                "quat_w": "1.0",
                "quat_x": "0.0",
                "quat_y": "0.0",
                "quat_z": "0.0",
                "quat_0": "1.0",
                "quat_1": "0.0",
                "quat_2": "0.0",
                "quat_3": "0.0",
                "gyro_x": "0.0",
                "gyro_y": "0.0",
                "gyro_z": "1.0" if kick else str(yaw_rate),
                "acc_x": "8.0" if kick else "0.0",
                "acc_y": "0.0",
                "acc_z": "9.80665",
                "roll_rad": "0.0",
                "pitch_rad": "0.0",
                "yaw_rad": "0.0",
                "mode": 2 if moving else 1,
                "gait_type": 1 if moving else 0,
                "go2_velocity_0": "0.05" if moving else "0.0",
                "go2_velocity_1": "0.0",
                "go2_velocity_2": "0.0",
                "yaw_speed_radps": str(yaw_rate),
                "source_role": "go2_body_state_diagnostic",
                "body_frame": "FLU",
                "accel_contains_gravity": "true",
                "quaternion_order": "wxyz",
                "rpy_order": "roll_pitch_yaw",
            }
            for foot in range(4):
                row[f"foot_force_{foot}"] = "30.0" if moving else "0.0"
            for foot in range(12):
                row[f"foot_speed_body_{foot}"] = "0.1" if moving else "0.0"
            writer.writerow(row)

    trace_header = [
        "timestamp",
        "lat_deg",
        "lon_deg",
        "height_m",
        "yaw_deg",
        "pitch_deg",
        "roll_deg",
        "source_role",
        "trace_solver_input",
        "trace_evaluation_only",
    ]
    with (out / "BY2_TRACE_REFERENCE_EVAL_ONLY.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=trace_header)
        writer.writeheader()
        for index in range(row_count):
            timestamp = start + index * dt
            move = max(0, index - 24)
            writer.writerow(
                {
                    "timestamp": f"{timestamp:.9f}",
                    "lat_deg": f"{lat0 + move * 1.0e-7:.12f}",
                    "lon_deg": f"{lon0 + move * 1.2e-7:.12f}",
                    "height_m": f"{height0 + move * 0.001:.6f}",
                    "yaw_deg": "0.0",
                    "pitch_deg": "0.0",
                    "roll_deg": "0.0",
                    "source_role": "evaluation_reference",
                    "trace_solver_input": "false",
                    "trace_evaluation_only": "true",
                }
            )
    manifest = {
        "phase": "N4G_toy",
        "toy_inputs": True,
        "event_normalized_time_axis": True,
        "clock_sync_claim": False,
        "physical_time_offset_claim": False,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "trace_used_for_alignment": False,
        "receiver_imu_as_body_imu": False,
        "raw_doppler_claim": False,
        "go2_prior_claim": False,
        "source_aware_weighting_claim": False,
        "fgo_smoother_claim": False,
        "numerical_performance_claim": False,
    }
    (out / "BY2_INPUT_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
