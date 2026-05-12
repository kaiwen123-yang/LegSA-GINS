"""N7B Go2 contact-state readiness diagnostics.

中文说明：contact labels 只用于 readiness/cross-source review；foot-force
threshold 是固定诊断默认值，不从 trace 或 final_v23 输出调参，也不在 N7B
激活 solver prior。
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


CONTACT_LABELS = [
    "standing_contact",
    "walking_contact",
    "swing_or_uncertain",
    "low_confidence",
    "invalid",
]


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _stats(values: list[float]) -> dict[str, float | None]:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return {"min": None, "p50": None, "p95": None, "max": None, "mean": None}
    return {
        "min": finite[0],
        "p50": finite[len(finite) // 2],
        "p95": finite[max(0, min(len(finite) - 1, math.ceil(0.95 * len(finite)) - 1))],
        "max": finite[-1],
        "mean": sum(finite) / len(finite),
    }


def _mode_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _standing_hint(row: dict[str, Any]) -> bool:
    mode = _mode_token(row.get("mode"))
    gait = _mode_token(row.get("gait_type"))
    text = f"{mode} {gait}"
    if any(token in text for token in ["stand", "idle", "static", "balance"]):
        return True
    try:
        return float(gait) == 0.0 and float(mode or 0.0) in {0.0, 1.0}
    except ValueError:
        return False


def _walking_hint(row: dict[str, Any]) -> bool:
    mode = _mode_token(row.get("mode"))
    gait = _mode_token(row.get("gait_type"))
    text = f"{mode} {gait}"
    if any(token in text for token in ["walk", "trot", "run", "move", "climb"]):
        return True
    try:
        return float(gait) > 0.0
    except ValueError:
        return False


def _foot_speed_norm(row: dict[str, Any], foot_index: int) -> float:
    base = 3 * foot_index
    values = [_f(row.get(f"foot_speed_body_{base + axis}")) for axis in range(3)]
    if any(not math.isfinite(value) for value in values):
        return math.nan
    return math.sqrt(sum(value * value for value in values))


def _time_value(row: dict[str, Any]) -> float:
    aligned = _f(row.get("aligned_time"))
    return aligned if math.isfinite(aligned) else _f(row.get("time"), 0.0)


def build_contact_state(
    rows: list[dict[str, Any]],
    *,
    force_threshold: float = 15.0,
    foot_speed_threshold: float = 0.35,
    min_contact_feet: int = 2,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Classify per-row contact state from Go2 high-level body-state fields."""

    out_rows: list[dict[str, Any]] = []
    per_foot_counts = [0, 0, 0, 0]
    per_foot_valid = [0, 0, 0, 0]
    force_values: list[float] = []
    speed_values: list[float] = []
    for index, row in enumerate(rows):
        forces = [_f(row.get(f"foot_force_{foot}")) for foot in range(4)]
        speeds = [_foot_speed_norm(row, foot) for foot in range(4)]
        contacts: list[bool] = []
        valid_feet = 0
        for foot, (force, speed) in enumerate(zip(forces, speeds)):
            valid = math.isfinite(force) or math.isfinite(speed)
            if valid:
                per_foot_valid[foot] += 1
                valid_feet += 1
            contact = math.isfinite(force) and force >= force_threshold
            if contact and math.isfinite(speed):
                contact = speed <= foot_speed_threshold
            if contact:
                per_foot_counts[foot] += 1
            contacts.append(contact)
            if math.isfinite(force):
                force_values.append(force)
            if math.isfinite(speed):
                speed_values.append(speed)
        contact_count = sum(1 for item in contacts if item)
        if valid_feet == 0:
            label = "invalid"
        elif contact_count >= 3 and (_standing_hint(row) or not _walking_hint(row)):
            label = "standing_contact"
        elif contact_count >= min_contact_feet and (_walking_hint(row) or contact_count < 4):
            label = "walking_contact"
        elif contact_count == 0:
            label = "swing_or_uncertain"
        else:
            label = "low_confidence"
        out_rows.append(
            {
                "row_index": index,
                "time": _time_value(row),
                "mode": row.get("mode", ""),
                "gait_type": row.get("gait_type", ""),
                "body_height": row.get("body_height", ""),
                "contact_label": label,
                "contact_count": contact_count,
                **{f"foot_{foot}_contact": int(contacts[foot]) for foot in range(4)},
                **{f"foot_{foot}_force": forces[foot] if math.isfinite(forces[foot]) else "" for foot in range(4)},
                **{f"foot_{foot}_speed_norm": speeds[foot] if math.isfinite(speeds[foot]) else "" for foot in range(4)},
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "go2_contact_prior_enabled": False,
            }
        )
    counts = Counter(row["contact_label"] for row in out_rows)
    total = len(out_rows)
    uncertain_count = counts["swing_or_uncertain"] + counts["low_confidence"] + counts["invalid"]
    per_foot_ratio = {
        f"foot_{foot}": (per_foot_counts[foot] / per_foot_valid[foot] if per_foot_valid[foot] else None)
        for foot in range(4)
    }
    uncertain_ratio = uncertain_count / total if total else 1.0
    invalid_ratio = counts["invalid"] / total if total else 1.0
    if not total or invalid_ratio > 0.50:
        quality = "not_ready"
    elif uncertain_ratio > 0.40:
        quality = "review"
    elif sum(1 for value in per_foot_ratio.values() if isinstance(value, float) and value > 0.10) < 2:
        quality = "review"
    else:
        quality = "ready"
    report: dict[str, Any] = {
        "stage": "N7B_go2_velocity_contact_readiness",
        "contact_rows": total,
        "standing_contact_ratio": counts["standing_contact"] / total if total else 0.0,
        "walking_contact_ratio": counts["walking_contact"] / total if total else 0.0,
        "swing_or_uncertain_ratio": counts["swing_or_uncertain"] / total if total else 0.0,
        "low_confidence_ratio": counts["low_confidence"] / total if total else 0.0,
        "invalid_ratio": invalid_ratio,
        "uncertain_ratio": uncertain_ratio,
        "per_foot_contact_ratio": per_foot_ratio,
        "foot_force_stats": _stats(force_values),
        "foot_speed_stats": _stats(speed_values),
        "force_threshold_role": "diagnostic_default_not_trace_tuned",
        "foot_speed_consistency_check": True,
        "recommended_contact_quality_status": quality,
        "contact_labels": CONTACT_LABELS,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_contact_prior_enabled": False,
        "paper_performance_claim": False,
    }
    return out_rows, report


def write_contact_state_outputs(
    rows: list[dict[str, Any]],
    output_dir: str | Path,
) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timeseries, report = build_contact_state(rows)
    csv_path = out / "GO2_CONTACT_STATE_TIMESERIES.csv"
    fieldnames = list(timeseries[0].keys()) if timeseries else [
        "row_index",
        "time",
        "contact_label",
        "contact_count",
        "trace_solver_input",
        "final_v23_output_solver_input",
        "go2_contact_prior_enabled",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timeseries)
    report_path = out / "GO2_CONTACT_STATE_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, timeseries, report
