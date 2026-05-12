"""Build runtime-only Go2 roll/pitch weak-prior CSV for N7A.

中文说明：N7A 只构造 roll/pitch weak prior；不启用 yaw/position/velocity
Go2 prior，不用 trace/final_v23 输出调权，也不做 output-only correction。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .go2_weak_prior_types import GO2_ATTITUDE_SOURCE_ID, Go2AttitudePriorPolicy


PRIOR_HEADER = [
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
]


def _as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _inside(value: float, start: float | None, end: float | None) -> bool:
    if start is None or end is None:
        return True
    return start <= value <= end


def build_go2_attitude_weak_priors(
    rows: list[dict[str, Any]],
    *,
    quaternion_report: dict[str, Any],
    frame_report: dict[str, Any],
    time_report: dict[str, Any],
    policy: Go2AttitudePriorPolicy | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = policy or Go2AttitudePriorPolicy()
    activation_allowed = bool(
        quaternion_report.get("activation_allowed_for_attitude_prior")
        and frame_report.get("activation_allowed")
        and time_report.get("activation_allowed")
    )
    blockers: list[str] = []
    if not quaternion_report.get("activation_allowed_for_attitude_prior"):
        blockers.append("quaternion_rpy_inconsistent")
    if not frame_report.get("activation_allowed"):
        blockers.append("frame_contract_blocked")
    if not time_report.get("activation_allowed"):
        blockers.append("time_alignment_blocked")
    overlap_start = time_report.get("overlap_start")
    overlap_end = time_report.get("overlap_end")
    priors: list[dict[str, Any]] = []
    for row in rows:
        time = _as_float(row.get("aligned_time"))
        roll = _as_float(row.get("roll_rad"))
        pitch = _as_float(row.get("pitch_rad"))
        if time is None or roll is None or pitch is None:
            continue
        if not _inside(time, overlap_start, overlap_end):
            continue
        foot_force_values = [_as_float(row.get(f"foot_force_{index}")) for index in range(4)]
        foot_force_sum = sum(value for value in foot_force_values if value is not None)
        quality = "nominal" if activation_allowed else "inactive_contract_blocked"
        if row.get("mode") in {"", None}:
            quality = "suspicious_missing_mode"
        priors.append(
            {
                "time": time,
                "roll_rad": roll,
                "pitch_rad": pitch,
                "std_roll_rad": cfg.std_roll_rad,
                "std_pitch_rad": cfg.std_pitch_rad,
                "source_status": "active" if activation_allowed else "inactive",
                "mode": row.get("mode", ""),
                "gait_type": row.get("gait_type", ""),
                "foot_force_sum": foot_force_sum,
                "body_height": row.get("body_height", ""),
                "quality_flag": quality,
            }
        )
    report = {
        "attitude_prior_csv_generated": True,
        "source_id": GO2_ATTITUDE_SOURCE_ID,
        "prior_count": len(priors),
        "valid_prior_count": sum(1 for row in priors if row["source_status"] == "active"),
        "std_policy": {
            "std_roll_deg": cfg.std_roll_deg,
            "std_pitch_deg": cfg.std_pitch_deg,
            "weak_prior": cfg.weak_prior,
            "diagnostic_only": cfg.diagnostic_only,
        },
        "yaw_prior_enabled": False,
        "position_prior_enabled": False,
        "velocity_prior_enabled": False,
        "activation_allowed": activation_allowed and bool(priors),
        "blocker_reasons": blockers,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
    }
    return priors, report


def write_go2_attitude_weak_priors(
    priors: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PRIOR_HEADER)
        writer.writeheader()
        for row in priors:
            writer.writerow({field: row.get(field, "") for field in PRIOR_HEADER})


def write_weak_prior_build_outputs(
    rows: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    quaternion_report: dict[str, Any],
    frame_report: dict[str, Any],
    time_report: dict[str, Any],
    policy: Go2AttitudePriorPolicy | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    out = Path(output_dir)
    priors, report = build_go2_attitude_weak_priors(
        rows,
        quaternion_report=quaternion_report,
        frame_report=frame_report,
        time_report=time_report,
        policy=policy,
    )
    csv_path = out / "GO2_ATTITUDE_WEAK_PRIORS.csv"
    report_path = out / "GO2_WEAK_PRIOR_BUILD_REPORT.json"
    write_go2_attitude_weak_priors(priors, csv_path)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, report
