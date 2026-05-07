"""N4F BY2 filter-core diagnostic trial adapters.

中文说明：
本模块只构造 diagnostic trial 输入。Go2 body-state gyro/accel 只作为基础滤波器
propagation input；receiver-native GNSS status 只作为 trial measurement；trace 与
final_v23 output 不在这里读取，也不进入 solver。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


IMU_INCREMENT_HEADER = [
    "timestamp",
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
]

RECEIVER_TRIAL_HEADER = [
    "timestamp",
    "tow",
    "lat_deg",
    "lon_deg",
    "height_m",
    "vn_mps",
    "ve_mps",
    "vd_mps",
    "yaw_deg",
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


def convert_go2_body_state_to_imu_increments(
    body_state_csv: str | Path,
    output_csv: str | Path,
    *,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Convert standardized BY2 Go2 body-state rows into IMU increments."""

    input_path = Path(body_state_csv)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped_nonpositive_dt = 0
    skipped_missing = 0
    previous_timestamp: float | None = None

    with input_path.open("r", encoding="utf-8", newline="") as source, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=IMU_INCREMENT_HEADER)
        writer.writeheader()

        for index, row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            timestamp = _as_float(row.get("timestamp"))
            gyro_x = _as_float(row.get("gyro_x"))
            gyro_y = _as_float(row.get("gyro_y"))
            gyro_z = _as_float(row.get("gyro_z"))
            acc_x = _as_float(row.get("acc_x"))
            acc_y = _as_float(row.get("acc_y"))
            acc_z = _as_float(row.get("acc_z"))
            if None in {timestamp, gyro_x, gyro_y, gyro_z, acc_x, acc_y, acc_z}:
                skipped_missing += 1
                continue
            if previous_timestamp is None:
                previous_timestamp = timestamp
                continue
            dt = timestamp - previous_timestamp
            previous_timestamp = timestamp
            if dt <= 0.0:
                skipped_nonpositive_dt += 1
                continue

            # FLU -> FRD exactly once: x unchanged, y/z sign-flipped.
            writer.writerow(
                {
                    "timestamp": f"{timestamp:.9f}",
                    "tow": f"{timestamp:.9f}",
                    "dt": f"{dt:.9f}",
                    "dtheta_x": f"{gyro_x * dt:.12g}",
                    "dtheta_y": f"{-gyro_y * dt:.12g}",
                    "dtheta_z": f"{-gyro_z * dt:.12g}",
                    "dvel_x": f"{acc_x * dt:.12g}",
                    "dvel_y": f"{-acc_y * dt:.12g}",
                    "dvel_z": f"{-acc_z * dt:.12g}",
                    "frame": "IMU_FRD_COMPATIBLE",
                    "source_role": "go2_body_state_diagnostic_imu_increment",
                }
            )
            written += 1

    return {
        "input": str(input_path),
        "output": str(output_path),
        "rows_written": written,
        "skipped_missing": skipped_missing,
        "skipped_nonpositive_dt": skipped_nonpositive_dt,
        "source_frame": "FLU",
        "output_frame": "IMU_FRD_COMPATIBLE",
        "transform_applied_once": True,
        "double_flu_to_frd": False,
        "receiver_imu_as_body_imu": False,
        "trace_solver_input": False,
    }


def make_receiver_measurement_trial_csv(
    gnss_status_standard_csv: str | Path,
    output_csv: str | Path,
    *,
    source_name: str,
) -> dict[str, Any]:
    """Create receiver-native measurement CSV for the N4F trial."""

    input_path = Path(gnss_status_standard_csv)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

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
            fallback_tow = _as_float(row.get("tow"))
            timestamp = _as_float(row.get("time_unix"), default=fallback_tow)
            tow = _as_float(row.get("tow"), default=timestamp)
            lat = _as_float(row.get("lat_deg"))
            lon = _as_float(row.get("lon_deg"))
            height = _as_float(row.get("height_m"))
            has_position = _as_bool(row.get("has_position")) and None not in {lat, lon, height}
            pos_std = _as_float(row.get("pos_acc_h_m"), default=10.0) or 10.0
            heading = _as_float(row.get("heading_deg"))
            has_heading = _as_bool(row.get("heading_valid")) and heading is not None
            rel_acc_n = _as_float(row.get("rel_acc_n_m"))
            rel_acc_e = _as_float(row.get("rel_acc_e_m"))
            yaw_std = 5.0
            if rel_acc_n is not None and rel_acc_e is not None:
                yaw_std = max(1.0, math.degrees(math.hypot(rel_acc_n, rel_acc_e)))

            if has_position:
                position_rows += 1
            if has_heading:
                heading_rows += 1
            writer.writerow(
                {
                    "timestamp": _csv_value(timestamp),
                    "tow": _csv_value(tow),
                    "lat_deg": _csv_value(lat),
                    "lon_deg": _csv_value(lon),
                    "height_m": _csv_value(height),
                    "vn_mps": "0.0",
                    "ve_mps": "0.0",
                    "vd_mps": "0.0",
                    "yaw_deg": _csv_value(heading if has_heading else 0.0),
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


def write_toy_standardized_inputs(output_dir: str | Path, *, row_count: int = 160) -> dict[str, Any]:
    """Write toy N4E-like standardized inputs for audits and tests only."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    start = 1000.0
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
                timestamp = start + index * dt
                writer.writerow(
                    {
                        "time_unix": f"{timestamp:.9f}",
                        "gps_week": 2409,
                        "tow": f"{timestamp:.9f}",
                        "lat_deg": f"{lat0 + index * 1.0e-7:.12f}",
                        "lon_deg": f"{lon0 + index * 1.2e-7:.12f}",
                        "height_m": f"{height0 + index * 0.001:.6f}",
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
                        "rel_valid": "true",
                        "ant_valid": "true",
                        "heading_deg": "0.0",
                        "heading_valid": "true",
                        "source_name": source_name,
                        "source_role": "receiver_native_gnss_status",
                    }
                )

    write_gnss(out / "BY2_GNSS1_STATUS_STANDARD.csv", "gnss1", True)
    write_gnss(out / "BY2_GNSS2_STATUS_STANDARD.csv", "gnss2", True)

    body_header = [
        "timestamp",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "acc_x",
        "acc_y",
        "acc_z",
        "source_role",
        "body_frame",
    ]
    with (out / "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=body_header)
        writer.writeheader()
        for index in range(row_count):
            timestamp = start + index * dt
            writer.writerow(
                {
                    "timestamp": f"{timestamp:.9f}",
                    "gyro_x": "0.0",
                    "gyro_y": "0.0",
                    "gyro_z": "0.0",
                    "acc_x": "0.0",
                    "acc_y": "0.0",
                    "acc_z": "0.0",
                    "source_role": "go2_body_state_diagnostic",
                    "body_frame": "FLU",
                }
            )

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
            writer.writerow(
                {
                    "timestamp": f"{timestamp:.9f}",
                    "lat_deg": f"{lat0 + index * 1.0e-7:.12f}",
                    "lon_deg": f"{lon0 + index * 1.2e-7:.12f}",
                    "height_m": f"{height0 + index * 0.001:.6f}",
                    "yaw_deg": "0.0",
                    "pitch_deg": "0.0",
                    "roll_deg": "0.0",
                    "source_role": "evaluation_reference",
                    "trace_solver_input": "false",
                    "trace_evaluation_only": "true",
                }
            )

    manifest = {
        "phase": "N4F_toy",
        "toy_inputs": True,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
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

