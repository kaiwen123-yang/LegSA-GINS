"""N7C3 bounded adaptive std policy for Go2 horizontal velocity.

中文说明：std 是测量不确定度，不是速度指令；N7C3 将水平速度 prior 的
std_vn/std_ve 限制在 1..5 m/s，不再使用 8/10 m/s 粗档位。vertical 继续
通过 std_vd=999 禁用，Go2 velocity 不是 truth。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


BOUNDED_PRIOR_FIELDS = [
    "time",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "confidence",
    "confidence_level",
    "update_flag",
    "reason_codes",
    "source_status",
    "quality_flag",
    "contact_model",
    "contact_label",
    "frame_candidate",
    "prior_policy",
    "diagnostic_only",
    "go2_velocity_truth_claim",
]


BASE_STD_MPS = 1.5
MIN_STD_MPS = 1.0
NORMAL_MAX_STD_MPS = 3.0
DIAGNOSTIC_EXTREME_MAX_STD_MPS = 5.0
STD_VD_DISABLED = 999.0


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _percentile(values: list[float], p: float) -> float:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return 0.0
    return finite[min(len(finite) - 1, int(p * (len(finite) - 1)))]


def bounded_std_for_confidence(confidence: float) -> tuple[float, bool, str]:
    """Return (std, update_flag, bucket_reason) for bounded N7C3 policy."""

    if confidence >= 0.80:
        return 1.0, True, "high_confidence_min_std"
    if confidence >= 0.60:
        return 1.5, True, "medium_confidence_base_std"
    if confidence >= 0.35:
        return 2.5, True, "low_confidence_soft_gated_normal_bound"
    if confidence >= 0.15:
        return 4.0, True, "very_low_confidence_soft_gated_extreme_bound"
    return 5.0, False, "invalid_confidence_hard_skip_diagnostic_cap"


def _confidence_by_time(confidence_rows: list[dict[str, Any]]) -> dict[float, dict[str, Any]]:
    return {round(_f(row.get("time"), 0.0), 6): row for row in confidence_rows}


def _nearest_confidence(row: dict[str, Any], confidence_rows: list[dict[str, Any]], by_time: dict[float, dict[str, Any]]) -> dict[str, Any]:
    key = round(_f(row.get("time"), 0.0), 6)
    if key in by_time:
        return by_time[key]
    time_value = _f(row.get("time"), 0.0)
    if not confidence_rows:
        return {"confidence": 0.0, "confidence_level": "invalid", "reason_codes": "confidence_missing"}
    best = min(confidence_rows, key=lambda item: abs(_f(item.get("time"), 0.0) - time_value))
    return best if abs(_f(best.get("time"), 0.0) - time_value) <= 0.25 else {"confidence": 0.0, "confidence_level": "invalid", "reason_codes": "confidence_missing"}


def build_bounded_adaptive_go2_horizontal_velocity_priors(
    *,
    source_prior_rows: list[dict[str, Any]],
    confidence_rows: list[dict[str, Any]],
    policy_name: str = "n7c3_bounded_adaptive_std_soft_gating",
    high_confidence_only: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build row-wise std/update_flag priors from confidence rows."""

    by_time = _confidence_by_time(confidence_rows)
    output_rows: list[dict[str, Any]] = []
    for row in source_prior_rows:
        conf_row = _nearest_confidence(row, confidence_rows, by_time)
        confidence = max(0.0, min(1.0, _f(conf_row.get("confidence"), 0.0)))
        std, update_flag, std_reason = bounded_std_for_confidence(confidence)
        confidence_level = str(conf_row.get("confidence_level") or "invalid")
        if high_confidence_only and confidence_level != "high":
            update_flag = False
            std = DIAGNOSTIC_EXTREME_MAX_STD_MPS
            std_reason = "high_confidence_only_skip"
        std = min(DIAGNOSTIC_EXTREME_MAX_STD_MPS, max(MIN_STD_MPS, std))
        reason_parts = [part for part in str(conf_row.get("reason_codes") or "").split(";") if part]
        reason_parts.append(std_reason)
        output_rows.append(
            {
                "time": _f(row.get("time"), 0.0),
                "vn": _f(row.get("vn"), 0.0),
                "ve": _f(row.get("ve"), 0.0),
                "vd": 0.0,
                "std_vn": std,
                "std_ve": std,
                "std_vd": STD_VD_DISABLED,
                "confidence": confidence,
                "confidence_level": confidence_level,
                "update_flag": _bool_text(update_flag),
                "reason_codes": ";".join(dict.fromkeys(reason_parts)),
                "source_status": "active" if update_flag else "inactive",
                "quality_flag": f"n7c3_bounded_{confidence_level}_confidence",
                "contact_model": row.get("contact_model", ""),
                "contact_label": row.get("contact_label", ""),
                "frame_candidate": row.get("frame_candidate", ""),
                "prior_policy": policy_name,
                "diagnostic_only": "false" if not high_confidence_only else "true",
                "go2_velocity_truth_claim": "false",
            }
        )
    std_vn_values = [_f(row.get("std_vn"), 0.0) for row in output_rows]
    std_ve_values = [_f(row.get("std_ve"), 0.0) for row in output_rows]
    update_count = sum(1 for row in output_rows if str(row.get("update_flag")).lower() == "true")
    skip_count = len(output_rows) - update_count
    counts = {level: sum(1 for row in output_rows if row.get("confidence_level") == level) for level in ["high", "medium", "low", "invalid"]}
    report = {
        "stage": "N7C3_go2_horizontal_velocity_bounded_adaptive_std",
        "policy_name": policy_name,
        "policy_type": "literature_informed_probability_contact_bounded_soft_gating",
        "base_std_mps": BASE_STD_MPS,
        "min_std_mps": MIN_STD_MPS,
        "normal_max_std_mps": NORMAL_MAX_STD_MPS,
        "diagnostic_extreme_max_std_mps": DIAGNOSTIC_EXTREME_MAX_STD_MPS,
        "std_rules": {
            "confidence_gte_0p80": 1.0,
            "confidence_gte_0p60": 1.5,
            "confidence_gte_0p35": 2.5,
            "confidence_gte_0p15": 4.0,
            "confidence_lt_0p15": "skip_with_5mps_diagnostic_cap",
        },
        "row_count": len(output_rows),
        "update_count_expected": update_count,
        "skip_count_expected": skip_count,
        "confidence_counts": counts,
        "std_vn_p50": _percentile(std_vn_values, 0.50),
        "std_vn_p95": _percentile(std_vn_values, 0.95),
        "std_vn_max": max(std_vn_values, default=0.0),
        "std_ve_p50": _percentile(std_ve_values, 0.50),
        "std_ve_p95": _percentile(std_ve_values, 0.95),
        "std_ve_max": max(std_ve_values, default=0.0),
        "max_std_le_5": max(std_vn_values + std_ve_values, default=0.0) <= DIAGNOSTIC_EXTREME_MAX_STD_MPS,
        "contains_8_or_10_mps_std": any(value in {8.0, 10.0} for value in std_vn_values + std_ve_values),
        "vertical_disabled": True,
        "std_vd": STD_VD_DISABLED,
        "go2_velocity_truth_claim": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "navigation_metric_feedback_tuning": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }
    return output_rows, report


def write_bounded_adaptive_prior_outputs(
    *,
    output_dir: str | Path,
    rows: list[dict[str, Any]],
    report: dict[str, Any],
    csv_name: str = "GO2_HORIZONTAL_VELOCITY_BOUNDED_ADAPTIVE_PRIORS.csv",
    report_name: str = "GO2_HORIZONTAL_VELOCITY_BOUNDED_ADAPTIVE_STD_REPORT.json",
) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / csv_name
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BOUNDED_PRIOR_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in BOUNDED_PRIOR_FIELDS} for row in rows])
    report_path = out / report_name
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path
