"""N7C5 Go2 full-field inventory for proprioceptive factor mining.

中文说明：本模块只盘点 Go2 本体字段可用性和动态范围；Go2 body-state
是 proprioceptive observation，不是 truth，也不作为 trace/final_v23 调参入口。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


FIELD_GROUPS = {
    "quaternion": ["quat_w", "quat_x", "quat_y", "quat_z"],
    "rpy": ["roll_rad", "pitch_rad", "yaw_rad"],
    "gyroscope": ["gyro_x", "gyro_y", "gyro_z"],
    "accelerometer": ["acc_x", "acc_y", "acc_z"],
    "position": ["go2_position_0", "go2_position_1", "go2_position_2"],
    "velocity": ["go2_velocity_0", "go2_velocity_1", "go2_velocity_2"],
    "yaw_speed": ["yaw_speed_radps"],
    "body_height": ["body_height"],
    "mode": ["mode"],
    "gait_type": ["gait_type"],
    "foot_force": [f"foot_force_{i}" for i in range(4)],
    "foot_position_body": [f"foot_position_body_{i}" for i in range(12)],
    "foot_speed_body": [f"foot_speed_body_{i}" for i in range(12)],
}

CATEGORICAL_FIELD_GROUPS = {"mode", "gait_type"}

ASSUMED_UNITS_AND_FRAMES = {
    "quaternion": "unit quaternion, Go2 body attitude candidate",
    "rpy": "radian roll/pitch/yaw, Go2 body attitude candidate",
    "gyroscope": "rad/s, body frame",
    "accelerometer": "m/s^2, body frame",
    "position": "m, Go2 internal odometry frame; not absolute truth",
    "velocity": "m/s, Go2 internal/body-state velocity; not truth",
    "yaw_speed": "rad/s, Go2 reported yaw-rate",
    "body_height": "m, Go2 body height estimate",
    "mode": "Unitree mode enum",
    "gait_type": "Unitree gait enum",
    "foot_force": "sensor force-like units per foot",
    "foot_position_body": "m, body frame, 4 feet x xyz",
    "foot_speed_body": "m/s, body frame, 4 feet x xyz",
}

CANDIDATE_USES = {
    "quaternion": ["frame rotation for foot kinematic velocity", "roll/pitch weak prior audit"],
    "rpy": ["roll/pitch proprioceptive weak factor", "yaw-rate derivative diagnostic"],
    "gyroscope": ["foot kinematic omega cross r", "yaw-rate consistency"],
    "accelerometer": ["motion state diagnostic only"],
    "position": ["relative odometry between-factor candidate only"],
    "velocity": ["horizontal velocity factor", "cross-source consistency"],
    "yaw_speed": ["yaw-rate between-factor candidate"],
    "body_height": ["mode/gait plausibility", "stance validity diagnostic"],
    "mode": ["factor gating"],
    "gait_type": ["factor gating"],
    "foot_force": ["contact probability", "stance weighting"],
    "foot_position_body": ["foot kinematic velocity candidate"],
    "foot_speed_body": ["foot kinematic velocity candidate", "slip risk"],
}


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _field_stats(rows: list[dict[str, Any]], columns: list[str], *, categorical: bool = False) -> dict[str, Any]:
    row_count = len(rows)
    values: list[float] = []
    present = 0
    present_slots = 0
    for row in rows:
        row_present = False
        for column in columns:
            if column in row and str(row.get(column, "")) != "":
                row_present = True
                present_slots += 1
                if not categorical:
                    value = _f(row.get(column), math.nan)
                    if math.isfinite(value):
                        values.append(value)
        present += int(row_present)
    finite_slots = present_slots if categorical else len(values)
    total_slots = max(1, row_count * len(columns))
    return {
        "available": present > 0 and finite_slots > 0,
        "row_count": row_count,
        "present_row_ratio": present / row_count if row_count else 0.0,
        "finite_ratio": finite_slots / total_slots,
        "missing_ratio": 1.0 - finite_slots / total_slots,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "dynamic_range": (max(values) - min(values)) if values else None,
    }


def _update_rate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    times = [_f(row.get("aligned_time", row.get("time")), math.nan) for row in rows]
    times = [value for value in times if math.isfinite(value)]
    if len(times) < 2:
        return {"rate_hz_p50": 0.0, "dt_p50": None, "time_span_sec": 0.0}
    dts = sorted(max(0.0, b - a) for a, b in zip(times, times[1:]) if b >= a)
    p50 = dts[len(dts) // 2] if dts else 0.0
    return {
        "rate_hz_p50": 1.0 / p50 if p50 > 0 else 0.0,
        "dt_p50": p50,
        "time_span_sec": max(times) - min(times),
    }


def build_go2_full_field_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {}
    for name, columns in FIELD_GROUPS.items():
        stats = _field_stats(rows, columns, categorical=name in CATEGORICAL_FIELD_GROUPS)
        stats["columns"] = columns
        stats["units_assumed_frame"] = ASSUMED_UNITS_AND_FRAMES[name]
        stats["candidate_factor_uses"] = CANDIDATE_USES[name]
        stats["not_truth"] = True
        fields[name] = stats
    return {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "row_count": len(rows),
        "update_rate": _update_rate(rows),
        "fields": fields,
        "all_required_groups_available": all(fields[name]["available"] for name in FIELD_GROUPS),
        "not_truth": True,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_roll_pitch_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_go2_full_field_inventory(path: str | Path, report: dict[str, Any]) -> Path:
    return write_json(path, report)
