"""Build N7C4 Go2 horizontal velocity strength-calibration prior CSVs.

中文说明：这里只改变 Go2 horizontal velocity prior 的 std/update_flag，
保持水平二维更新、禁用垂向/yaw/position，且 Go2 velocity 不是 truth。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_horizontal_velocity_bounded_adaptive_std import BOUNDED_PRIOR_FIELDS, STD_VD_DISABLED


FIXED_STRENGTH_POLICIES = {
    "fixed_std_2p0": 2.0,
    "fixed_std_1p5": 1.5,
    "fixed_std_1p0": 1.0,
    "fixed_std_0p75_aggressive": 0.75,
}

ADAPTIVE_POLICIES = {
    "recalibrated_adaptive": {"high": 1.0, "medium": 1.5, "low": 2.5},
    "recalibrated_adaptive_aggressive": {"high": 0.75, "medium": 1.25, "low": 2.0},
}

STRENGTH_PRIOR_FILENAMES = {
    "fixed_std_2p0": "GO2_HORIZONTAL_VELOCITY_STRENGTH_FIXED_2P0_PRIORS.csv",
    "fixed_std_1p5": "GO2_HORIZONTAL_VELOCITY_STRENGTH_FIXED_1P5_PRIORS.csv",
    "fixed_std_1p0": "GO2_HORIZONTAL_VELOCITY_STRENGTH_FIXED_1P0_PRIORS.csv",
    "fixed_std_0p75_aggressive": "GO2_HORIZONTAL_VELOCITY_STRENGTH_FIXED_0P75_PRIORS.csv",
    "recalibrated_adaptive": "GO2_HORIZONTAL_VELOCITY_STRENGTH_RECALIBRATED_ADAPTIVE_PRIORS.csv",
    "recalibrated_adaptive_aggressive": "GO2_HORIZONTAL_VELOCITY_STRENGTH_RECALIBRATED_ADAPTIVE_AGGRESSIVE_PRIORS.csv",
}


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


def _confidence_by_time(confidence_rows: list[dict[str, Any]]) -> dict[float, dict[str, Any]]:
    return {round(_f(row.get("time"), 0.0), 6): row for row in confidence_rows}


def _nearest_confidence(source_row: dict[str, Any], confidence_rows: list[dict[str, Any]], by_time: dict[float, dict[str, Any]]) -> dict[str, Any]:
    time_value = _f(source_row.get("time"), 0.0)
    key = round(time_value, 6)
    if key in by_time:
        return by_time[key]
    if not confidence_rows:
        return {"confidence": 0.0, "confidence_level": "invalid", "reason_codes": "confidence_missing"}
    best = min(confidence_rows, key=lambda row: abs(_f(row.get("time"), 0.0) - time_value))
    if abs(_f(best.get("time"), 0.0) - time_value) <= 0.25:
        return best
    return {"confidence": 0.0, "confidence_level": "invalid", "reason_codes": "confidence_missing"}


def _row(
    *,
    source: dict[str, Any],
    confidence_row: dict[str, Any],
    policy_name: str,
    std: float,
    update_flag: bool,
    reason: str,
) -> dict[str, Any]:
    level = str(confidence_row.get("confidence_level") or "invalid")
    reason_parts = [part for part in str(confidence_row.get("reason_codes") or "").split(";") if part]
    reason_parts.append(reason)
    return {
        "time": _f(source.get("time"), 0.0),
        "vn": _f(source.get("vn"), 0.0),
        "ve": _f(source.get("ve"), 0.0),
        "vd": 0.0,
        "std_vn": std,
        "std_ve": std,
        "std_vd": STD_VD_DISABLED,
        "confidence": _f(confidence_row.get("confidence"), 0.0),
        "confidence_level": level,
        "update_flag": _bool_text(update_flag),
        "reason_codes": ";".join(dict.fromkeys(reason_parts)),
        "source_status": "active" if update_flag else "inactive",
        "quality_flag": f"n7c4_{policy_name}_{level}",
        "contact_model": source.get("contact_model", ""),
        "contact_label": source.get("contact_label", ""),
        "frame_candidate": source.get("frame_candidate", ""),
        "prior_policy": f"n7c4_{policy_name}",
        "diagnostic_only": "false",
        "go2_velocity_truth_claim": "false",
    }


def build_strength_prior_rows(
    *,
    source_prior_rows: list[dict[str, Any]],
    confidence_rows: list[dict[str, Any]],
    policy_name: str,
) -> list[dict[str, Any]]:
    by_time = _confidence_by_time(confidence_rows)
    rows: list[dict[str, Any]] = []
    for source in source_prior_rows:
        confidence_row = _nearest_confidence(source, confidence_rows, by_time)
        level = str(confidence_row.get("confidence_level") or "invalid")
        if policy_name in FIXED_STRENGTH_POLICIES:
            std = FIXED_STRENGTH_POLICIES[policy_name]
            update = True
            reason = f"{policy_name}_controlled_strength_scan"
        else:
            table = ADAPTIVE_POLICIES[policy_name]
            if level == "invalid":
                std = max(table.values())
                update = False
                reason = f"{policy_name}_invalid_skip"
            else:
                std = table.get(level, table["low"])
                update = True
                reason = f"{policy_name}_{level}_bounded_soft_gate"
        rows.append(_row(source=source, confidence_row=confidence_row, policy_name=policy_name, std=std, update_flag=update, reason=reason))
    return rows


def summarize_strength_prior_rows(rows: list[dict[str, Any]], policy_name: str) -> dict[str, Any]:
    std_vn = [_f(row.get("std_vn"), 0.0) for row in rows]
    std_ve = [_f(row.get("std_ve"), 0.0) for row in rows]
    update_count = sum(1 for row in rows if str(row.get("update_flag")).lower() == "true")
    skip_count = len(rows) - update_count
    return {
        "policy_name": policy_name,
        "row_count": len(rows),
        "update_count_expected": update_count,
        "skip_count_expected": skip_count,
        "std_vn_p50": _percentile(std_vn, 0.50),
        "std_vn_p95": _percentile(std_vn, 0.95),
        "std_vn_max": max(std_vn, default=0.0),
        "std_ve_p50": _percentile(std_ve, 0.50),
        "std_ve_p95": _percentile(std_ve, 0.95),
        "std_ve_max": max(std_ve, default=0.0),
        "confidence_counts": {level: sum(1 for row in rows if row.get("confidence_level") == level) for level in ["high", "medium", "low", "invalid"]},
        "horizontal_only": True,
        "vertical_disabled": True,
        "std_vd": STD_VD_DISABLED,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "go2_velocity_truth_claim": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }


def write_strength_prior_csv(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BOUNDED_PRIOR_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in BOUNDED_PRIOR_FIELDS} for row in rows])
    return output


def build_and_write_strength_priors(
    *,
    output_dir: str | Path,
    source_prior_rows: list[dict[str, Any]],
    confidence_rows: list[dict[str, Any]],
) -> tuple[dict[str, Path], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    prior_paths: dict[str, Path] = {}
    policy_reports: dict[str, Any] = {}
    for policy_name in [*FIXED_STRENGTH_POLICIES, *ADAPTIVE_POLICIES]:
        rows = build_strength_prior_rows(source_prior_rows=source_prior_rows, confidence_rows=confidence_rows, policy_name=policy_name)
        prior_paths[policy_name] = write_strength_prior_csv(out / STRENGTH_PRIOR_FILENAMES[policy_name], rows)
        policy_reports[policy_name] = summarize_strength_prior_rows(rows, policy_name)
    report = {
        "stage": "N7C4_go2_horizontal_velocity_strength_calibration",
        "policy_reports": policy_reports,
        "variant_std_policies": {
            **{name: {"std_vn": std, "std_ve": std, "std_vd": STD_VD_DISABLED} for name, std in FIXED_STRENGTH_POLICIES.items()},
            **{name: {**table, "invalid": "skip", "std_vd": STD_VD_DISABLED} for name, table in ADAPTIVE_POLICIES.items()},
        },
        "output_csvs": {name: path.name for name, path in prior_paths.items()},
        "horizontal_only": True,
        "vertical_disabled": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "go2_velocity_truth_claim": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }
    (out / "GO2_HORIZONTAL_VELOCITY_STRENGTH_PRIOR_BUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return prior_paths, report
