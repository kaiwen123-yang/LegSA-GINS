"""N7B Go2 motion-state readiness diagnostics.

中文说明：motion state 来自 Go2 高层状态、速度和足端诊断量，仅用于 N7B
readiness review，不读取 trace。
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .go2_contact_state import _f


MOTION_LABELS = ["standing", "low_speed_motion", "walking", "turn_in_place", "uncertain"]


def _time_value(row: dict[str, Any]) -> float:
    aligned = _f(row.get("aligned_time"))
    return aligned if math.isfinite(aligned) else _f(row.get("time"), 0.0)


def _speed_norm(row: dict[str, Any]) -> float:
    values = [_f(row.get(f"go2_velocity_{axis}")) for axis in range(3)]
    return math.sqrt(sum(value * value for value in values)) if all(math.isfinite(value) for value in values) else math.nan


def _walking_hint(row: dict[str, Any]) -> bool:
    text = f"{row.get('mode', '')} {row.get('gait_type', '')}".lower()
    if any(token in text for token in ["walk", "trot", "run", "move"]):
        return True
    try:
        return float(row.get("gait_type", 0.0) or 0.0) > 0.0
    except ValueError:
        return False


def _force_contact_count(row: dict[str, Any], force_threshold: float = 15.0) -> int:
    return sum(1 for foot in range(4) if _f(row.get(f"foot_force_{foot}")) >= force_threshold)


def classify_motion_state(row: dict[str, Any]) -> str:
    speed = _speed_norm(row)
    yaw_speed = abs(_f(row.get("yaw_speed_radps"), 0.0))
    contact_count = _force_contact_count(row)
    if not math.isfinite(speed):
        return "uncertain"
    if speed < 0.08 and yaw_speed < 0.08 and contact_count >= 2:
        return "standing"
    if speed < 0.25 and yaw_speed >= 0.25:
        return "turn_in_place"
    if speed < 0.25:
        return "low_speed_motion"
    if speed >= 0.25 or _walking_hint(row):
        return "walking"
    return "uncertain"


def analyze_motion_state(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    timeseries: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        label = classify_motion_state(row)
        timeseries.append(
            {
                "row_index": index,
                "time": _time_value(row),
                "motion_state": label,
                "go2_speed_norm": _speed_norm(row),
                "yaw_speed_abs": abs(_f(row.get("yaw_speed_radps"), 0.0)),
                "mode": row.get("mode", ""),
                "gait_type": row.get("gait_type", ""),
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "go2_velocity_prior_enabled": False,
                "go2_yaw_prior_enabled": False,
            }
        )
    counts = Counter(row["motion_state"] for row in timeseries)
    total = len(timeseries)
    report = {
        "stage": "N7B_go2_velocity_contact_readiness",
        "motion_rows": total,
        "standing_ratio": counts["standing"] / total if total else 0.0,
        "low_speed_motion_ratio": counts["low_speed_motion"] / total if total else 0.0,
        "walking_ratio": counts["walking"] / total if total else 0.0,
        "turn_in_place_ratio": counts["turn_in_place"] / total if total else 0.0,
        "uncertain_ratio": counts["uncertain"] / total if total else 1.0,
        "motion_labels": MOTION_LABELS,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    return timeseries, report


def write_motion_state_outputs(rows: list[dict[str, Any]], output_dir: str | Path) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timeseries, report = analyze_motion_state(rows)
    csv_path = out / "GO2_MOTION_STATE_TIMESERIES.csv"
    fieldnames = list(timeseries[0].keys()) if timeseries else ["row_index", "time", "motion_state"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timeseries)
    report_path = out / "GO2_MOTION_STATE_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, timeseries, report
