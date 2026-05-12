"""Parse Go2 sportmodestate/body-state text for N7A.

中文说明：本模块只标准化 Go2 body-state 内部状态；position/velocity 是
Go2 odometry/high-level state，不是全局真值，不进入 N7A EKF 位置/速度先验。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.datasets.by2.go2_body_state_parser import parse_go2_body_state_text

from .go2_weak_prior_types import GO2_SOURCE_ROLE


STANDARDIZED_HEADER = [
    "stamp_sec",
    "stamp_nanosec",
    "time",
    "aligned_time",
    "quat_w",
    "quat_x",
    "quat_y",
    "quat_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "acc_x",
    "acc_y",
    "acc_z",
    "roll_rad",
    "pitch_rad",
    "yaw_rad",
    "temperature",
    "mode",
    "gait_type",
    "foot_raise_height",
    "go2_position_0",
    "go2_position_1",
    "go2_position_2",
    "body_height",
    "go2_velocity_0",
    "go2_velocity_1",
    "go2_velocity_2",
    "yaw_speed_radps",
    "foot_force_0",
    "foot_force_1",
    "foot_force_2",
    "foot_force_3",
    *[f"foot_position_body_{index}" for index in range(12)],
    *[f"foot_speed_body_{index}" for index in range(12)],
    "source_role",
    "not_truth",
]


def _as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        value_float = float(value)
    except (TypeError, ValueError):
        return None
    return value_float if math.isfinite(value_float) else None


def _present(rows: list[dict[str, Any]], fields: list[str]) -> bool:
    return any(all(_as_float(row.get(field)) is not None for field in fields) for row in rows)


def _stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p50": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[int(0.95 * (len(ordered) - 1))],
        "max": ordered[-1],
    }


def _time_range(rows: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    values = [_as_float(row.get(key)) for row in rows]
    values = [value for value in values if value is not None]
    return {
        "start": min(values) if values else None,
        "end": max(values) if values else None,
    }


def standardize_go2_body_state(
    input_path: str | Path,
    *,
    base_time: float | None = None,
    max_messages: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return standardized rows and a source-integrity report."""

    parsed = parse_go2_body_state_text(input_path, max_messages=max_messages)
    times = [_as_float(row.get("timestamp")) for row in parsed]
    times = [value for value in times if value is not None]
    base = base_time if base_time is not None else (times[0] if times else 0.0)
    rows: list[dict[str, Any]] = []
    for row in parsed:
        timestamp = _as_float(row.get("timestamp"))
        out = {field: row.get(field) for field in STANDARDIZED_HEADER}
        out["time"] = timestamp
        out["aligned_time"] = None if timestamp is None else timestamp - base
        out["body_height"] = row.get("body_height")
        out["source_role"] = GO2_SOURCE_ROLE
        out["not_truth"] = True
        rows.append(out)
    aligned = [_as_float(row.get("aligned_time")) for row in rows]
    aligned = [value for value in aligned if value is not None]
    dt = [b - a for a, b in zip(aligned, aligned[1:]) if b >= a]
    report = {
        "row_count": len(rows),
        "time_range": _time_range(rows, "time"),
        "aligned_time_range": _time_range(rows, "aligned_time"),
        "base_time": base,
        "base_time_role": "go2_first_stamp_or_runtime_argument_not_trace",
        "dt_stats": _stats(dt),
        "quaternion_found": _present(rows, ["quat_w", "quat_x", "quat_y", "quat_z"]),
        "rpy_found": _present(rows, ["roll_rad", "pitch_rad", "yaw_rad"]),
        "gyro_found": _present(rows, ["gyro_x", "gyro_y", "gyro_z"]),
        "accel_found": _present(rows, ["acc_x", "acc_y", "acc_z"]),
        "position_found": _present(rows, ["go2_position_0", "go2_position_1", "go2_position_2"]),
        "velocity_found": _present(rows, ["go2_velocity_0", "go2_velocity_1", "go2_velocity_2"]),
        "yaw_speed_found": _present(rows, ["yaw_speed_radps"]),
        "foot_force_found": _present(rows, [f"foot_force_{index}" for index in range(4)]),
        "mode_found": any(str(row.get("mode") or "").strip() for row in rows),
        "gait_type_found": any(str(row.get("gait_type") or "").strip() for row in rows),
        "source_role": GO2_SOURCE_ROLE,
        "not_truth": True,
        "position_velocity_navigation_measurement": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }
    return rows, report


def write_standardized_csv(rows: list[dict[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STANDARDIZED_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in STANDARDIZED_HEADER})


def write_parse_outputs(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    base_time: float | None = None,
    max_messages: int | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    out = Path(output_dir)
    rows, report = standardize_go2_body_state(input_path, base_time=base_time, max_messages=max_messages)
    csv_path = out / "GO2_BODY_STATE_STANDARDIZED.csv"
    report_path = out / "GO2_BODY_STATE_PARSE_REPORT.json"
    write_standardized_csv(rows, csv_path)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, report


def read_standardized_csv(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
