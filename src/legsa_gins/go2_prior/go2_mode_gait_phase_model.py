"""N7C5 mode/gait phase model for Go2 proprioceptive gating.

中文说明：phase 只用于候选因子 gating/std scaling 诊断，不作为 truth。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


PHASE_FIELDS = ["time", "mode", "gait_type", "velocity_norm", "yaw_speed_abs", "body_height", "support_probability", "phase", "reason_codes"]


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _nearest_by_time(rows: list[dict[str, Any]], time_value: float, start: int, tol: float) -> tuple[dict[str, Any] | None, int]:
    if not rows:
        return None, start
    index = max(0, min(start, len(rows) - 1))
    while index + 1 < len(rows) and abs(_f(rows[index + 1].get("time"), 0.0) - time_value) <= abs(_f(rows[index].get("time"), 0.0) - time_value):
        index += 1
    return (rows[index] if abs(_f(rows[index].get("time"), 0.0) - time_value) <= tol else None), index


def classify_phase(row: dict[str, Any], contact: dict[str, Any] | None = None) -> tuple[str, str]:
    vx = _f(row.get("go2_velocity_0"), 0.0)
    vy = _f(row.get("go2_velocity_1"), 0.0)
    vz = _f(row.get("go2_velocity_2"), 0.0)
    speed = math.sqrt(vx * vx + vy * vy + vz * vz)
    yaw_abs = abs(_f(row.get("yaw_speed_radps"), 0.0))
    support = _f((contact or {}).get("support_probability"), math.nan)
    mode = str(row.get("mode") or "")
    gait = str(row.get("gait_type") or "")
    if not mode or not gait:
        return "uncertain", "mode_or_gait_missing"
    if yaw_abs > 0.35 and speed < 0.50:
        return "turning", "yaw_speed_high_low_translation"
    if speed < 0.08 and (not math.isfinite(support) or support > 0.35):
        return "standing", "low_velocity_support_available"
    if speed > 0.15 and yaw_abs <= 0.35:
        return "walking", "translation_motion"
    if math.isfinite(support) and support < 0.20:
        return "transition", "low_support_probability"
    return "uncertain", "mixed_mode_gait_evidence"


def build_go2_mode_gait_phase_model(go2_rows: list[dict[str, Any]], contact_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contacts = sorted(contact_rows, key=lambda row: _f(row.get("time"), 0.0))
    idx = 0
    out: list[dict[str, Any]] = []
    for row in sorted(go2_rows, key=lambda item: _f(item.get("aligned_time", item.get("time")), 0.0)):
        time_value = _f(row.get("aligned_time", row.get("time")), 0.0)
        contact, idx = _nearest_by_time(contacts, time_value, idx, 0.25)
        phase, reason = classify_phase(row, contact)
        vx = _f(row.get("go2_velocity_0"), 0.0)
        vy = _f(row.get("go2_velocity_1"), 0.0)
        vz = _f(row.get("go2_velocity_2"), 0.0)
        out.append(
            {
                "time": time_value,
                "mode": row.get("mode", ""),
                "gait_type": row.get("gait_type", ""),
                "velocity_norm": math.sqrt(vx * vx + vy * vy + vz * vz),
                "yaw_speed_abs": abs(_f(row.get("yaw_speed_radps"), 0.0)),
                "body_height": _f(row.get("body_height"), 0.0),
                "support_probability": _f((contact or {}).get("support_probability"), 0.0),
                "phase": phase,
                "reason_codes": reason,
            }
        )
    counts = {phase: sum(1 for row in out if row["phase"] == phase) for phase in ["standing", "walking", "turning", "uncertain", "transition"]}
    report = {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "row_count": len(out),
        "phase_counts": counts,
        "factor_gating_ready": len(out) > 0 and (counts["walking"] + counts["standing"] + counts["turning"]) > 0,
        "not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    return out, report


def write_go2_mode_gait_phase_outputs(output_dir: str | Path, rows: list[dict[str, Any]], report: dict[str, Any]) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "GO2_MODE_GAIT_PHASE_TIMESERIES.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PHASE_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in PHASE_FIELDS} for row in rows])
    report_path = out / "GO2_MODE_GAIT_PHASE_MODEL_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path
