"""N7C6 Go2 roll/pitch attitude strength calibration helpers.

中文说明：这里只构造 roll/pitch proprioceptive observation prior；Go2 roll/pitch
不是 truth，不启用 yaw/position/vertical velocity，也不使用 trace/final_v23 调参。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


ATTITUDE_STD_POLICIES_DEG = {
    "rp5deg": 5.0,
    "rp3deg": 3.0,
    "rp1p6deg": 1.6,
    "rp1deg": 1.0,
    "rp0p75deg": 0.75,
}

ATTITUDE_PRIOR_FIELDS = [
    "time",
    "roll_rad",
    "pitch_rad",
    "std_roll_rad",
    "std_pitch_rad",
    "source_status",
    "mode",
    "gait_type",
    "foot_force_sum",
    "body_height",
    "quality_flag",
    "go2_roll_pitch_truth_claim",
]


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _rad(deg: float) -> float:
    return deg * math.pi / 180.0


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def build_attitude_strength_prior_rows(go2_rows: list[dict[str, Any]], *, std_deg: float) -> list[dict[str, Any]]:
    std_rad = _rad(std_deg)
    out: list[dict[str, Any]] = []
    for row in go2_rows:
        time = _f(row.get("aligned_time", row.get("time")), math.nan)
        roll = _f(row.get("roll_rad"), math.nan)
        pitch = _f(row.get("pitch_rad"), math.nan)
        if not all(math.isfinite(value) for value in [time, roll, pitch]):
            continue
        foot_force_sum = sum(_f(row.get(f"foot_force_{foot}"), 0.0) for foot in range(4))
        out.append(
            {
                "time": time,
                "roll_rad": roll,
                "pitch_rad": pitch,
                "std_roll_rad": std_rad,
                "std_pitch_rad": std_rad,
                "source_status": "active",
                "mode": row.get("mode", ""),
                "gait_type": row.get("gait_type", ""),
                "foot_force_sum": foot_force_sum,
                "body_height": row.get("body_height", ""),
                "quality_flag": f"n7c6_attitude_strength_{std_deg:g}deg",
                "go2_roll_pitch_truth_claim": "false",
            }
        )
    return out


def summarize_attitude_prior_rows(rows: list[dict[str, Any]], *, std_deg: float) -> dict[str, Any]:
    return {
        "std_roll_deg": std_deg,
        "std_pitch_deg": std_deg,
        "std_roll_rad": _rad(std_deg),
        "std_pitch_rad": _rad(std_deg),
        "row_count": len(rows),
        "active_count": sum(1 for row in rows if str(row.get("source_status")) == "active"),
        "go2_roll_pitch_truth_claim": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_attitude_prior_csv(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ATTITUDE_PRIOR_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in ATTITUDE_PRIOR_FIELDS} for row in rows])
    return output


def write_attitude_strength_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
