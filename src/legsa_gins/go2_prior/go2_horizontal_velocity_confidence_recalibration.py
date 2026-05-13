"""N7C4 recalibrated confidence for Go2 horizontal velocity strength scan.

中文说明：本模块放宽 N7C3 过保守的 harmonic/min 组合，但仍只使用
solver-visible / cross-source consistency 信息，不读取 trace 或 final_v23 输出调参。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_horizontal_velocity_confidence import read_csv_rows, read_json


RECALIBRATED_CONFIDENCE_FIELDS = [
    "time",
    "vn",
    "ve",
    "vd",
    "confidence",
    "confidence_level",
    "contact_confidence",
    "frame_confidence",
    "receiver_consistency_confidence",
    "raw_doppler_consistency_confidence",
    "cross_source_consistency_confidence",
    "time_alignment_confidence",
    "residual_consistency_confidence",
    "contact_probability",
    "frame_horizontal_difference_mps",
    "go2_minus_receiver_horizontal_mps",
    "go2_minus_raw_horizontal_mps",
    "source_aware_residual_norm",
    "source_aware_normalized_innovation",
    "mode",
    "gait_type",
    "reason_codes",
    "no_truth_claim",
    "no_trace_tuning",
    "no_final_v23_tuning",
]


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _clamp01(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _time(row: dict[str, Any]) -> float:
    return _f(row.get("time"), 0.0)


def _nearest(rows: list[dict[str, Any]], time_value: float, start_index: int, tolerance: float) -> tuple[dict[str, Any] | None, int, float]:
    if not rows or not math.isfinite(time_value):
        return None, start_index, math.inf
    index = max(0, min(start_index, len(rows) - 1))
    while index + 1 < len(rows) and abs(_time(rows[index + 1]) - time_value) <= abs(_time(rows[index]) - time_value):
        index += 1
    best = rows[index]
    diff = abs(_time(best) - time_value)
    return (best if diff <= tolerance else None), index, diff


def _horizontal_diff(a_vn: float, a_ve: float, b_vn: float, b_ve: float) -> float:
    if not all(math.isfinite(value) for value in [a_vn, a_ve, b_vn, b_ve]):
        return math.nan
    return math.hypot(a_vn - b_vn, a_ve - b_ve)


def _consistency_from_diff(diff_mps: float | None) -> float:
    if diff_mps is None or not math.isfinite(diff_mps):
        return 0.50
    if diff_mps <= 0.50:
        return 1.00
    if diff_mps <= 1.00:
        return 0.85
    if diff_mps <= 1.75:
        return 0.65
    if diff_mps <= 3.00:
        return 0.38
    if diff_mps <= 5.00:
        return 0.18
    return 0.05


def _time_confidence(max_dt: float) -> float:
    if not math.isfinite(max_dt):
        return 0.40
    if max_dt <= 0.05:
        return 1.00
    if max_dt <= 0.10:
        return 0.90
    if max_dt <= 0.25:
        return 0.70
    if max_dt <= 0.55:
        return 0.35
    return 0.05


def _contact_confidence(row: dict[str, Any] | None) -> tuple[float, float, str, str]:
    if not row:
        return 0.45, math.nan, "", ""
    support = _clamp01(_f(row.get("support_probability"), 0.0))
    score = _clamp01(_f(row.get("confidence_score"), 0.0))
    uncertainty = _clamp01(_f(row.get("uncertainty_probability"), 0.5))
    value = _clamp01(0.55 * support + 0.35 * score + 0.10 * (1.0 - uncertainty))
    return value, support, str(row.get("mode") or ""), str(row.get("gait_type") or "")


def _frame_confidence(row: dict[str, Any] | None, report: dict[str, Any]) -> tuple[float, float]:
    base = 0.85 if report.get("frame_equivalent_for_horizontal_only") else 0.60
    if not row:
        return base, math.nan
    hdiff = _f(row.get("horizontal_difference_mps"), math.nan)
    angle = abs(_f(row.get("horizontal_angle_difference_deg"), math.nan))
    diff_score = 1.0 - min(1.0, hdiff / 1.50) if math.isfinite(hdiff) else base
    angle_score = 1.0 - min(1.0, angle / 35.0) if math.isfinite(angle) else base
    return _clamp01(0.40 * base + 0.35 * diff_score + 0.25 * angle_score), hdiff


def _residual_confidence(row: dict[str, Any] | None) -> tuple[float, float, float]:
    if not row:
        return 0.65, math.nan, math.nan
    residual = _f(row.get("residual_norm"), math.nan)
    normalized = _f(row.get("normalized_innovation"), math.nan)
    if math.isfinite(normalized):
        if normalized <= 1.0:
            return 1.0, residual, normalized
        if normalized <= 2.0:
            return 0.80, residual, normalized
        if normalized <= 4.0:
            return 0.45, residual, normalized
        return 0.15, residual, normalized
    if math.isfinite(residual):
        return _consistency_from_diff(residual), residual, normalized
    return 0.65, residual, normalized


def _source_rows_for_selected_model(rows: list[dict[str, Any]], report: dict[str, Any]) -> list[dict[str, Any]]:
    selected = str(report.get("selected_contact_probability_model") or "")
    if selected:
        filtered = [row for row in rows if str(row.get("model_id") or "") == selected]
        if filtered:
            return sorted(filtered, key=_time)
    return sorted(rows, key=_time)


def _confidence_level(
    *,
    confidence: float,
    valid: bool,
    frame_confidence: float,
    time_confidence: float,
    cross_confidence: float,
    contact_confidence: float,
) -> str:
    if not valid or confidence < 0.15:
        return "invalid"
    if frame_confidence >= 0.75 and time_confidence >= 0.75 and cross_confidence >= 0.75 and contact_confidence >= 0.25:
        return "high"
    if frame_confidence >= 0.65 and time_confidence >= 0.60 and cross_confidence >= 0.45:
        return "medium"
    return "low"


def _reason_codes(
    *,
    level: str,
    contact_confidence: float,
    frame_confidence: float,
    cross_confidence: float,
    time_confidence: float,
    residual_confidence: float,
    receiver_diff: float | None,
    raw_diff: float | None,
) -> str:
    reasons: list[str] = []
    if level == "high":
        reasons.append("frame_time_cross_source_locally_good")
    if contact_confidence < 0.25:
        reasons.append("contact_confidence_low_not_forced_invalid")
    if frame_confidence < 0.65:
        reasons.append("frame_equivalence_moderate_or_weak")
    if cross_confidence < 0.45:
        reasons.append("cross_source_difference_large")
    if time_confidence < 0.60:
        reasons.append("time_alignment_moderate_or_weak")
    if residual_confidence < 0.45:
        reasons.append("solver_visible_residual_consistency_weak")
    if receiver_diff is None and raw_diff is None:
        reasons.append("cross_source_rows_missing")
    if level == "invalid":
        reasons.append("invalid_for_hard_skip")
    if not reasons:
        reasons.append("recalibrated_soft_gate_nominal")
    reasons.extend(["no_trace_tuning", "no_final_v23_tuning", "go2_velocity_not_truth"])
    return ";".join(dict.fromkeys(reasons))


def load_go2_source_aware_residual_rows(*roots: str | Path) -> list[dict[str, Any]]:
    """Load solver-produced Go2 horizontal residual diagnostics when present."""

    rows: list[dict[str, Any]] = []
    for root in roots:
        base = Path(root)
        if not base.exists():
            continue
        for path in sorted(base.rglob("SOURCE_AWARE_WEIGHT_TRACE.csv")):
            for row in read_csv_rows(path):
                if str(row.get("source_id") or "") == "go2_horizontal_velocity":
                    rows.append(row)
    return sorted(rows, key=_time)


def build_go2_horizontal_velocity_recalibrated_confidence(
    *,
    prior_rows: list[dict[str, Any]],
    contact_probability_rows: list[dict[str, Any]],
    contact_probability_report: dict[str, Any],
    frame_equivalence_rows: list[dict[str, Any]],
    frame_equivalence_report: dict[str, Any],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    residual_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build recalibrated confidence rows without final metric feedback."""

    contact_rows = _source_rows_for_selected_model(contact_probability_rows, contact_probability_report)
    frame_rows = sorted(frame_equivalence_rows, key=_time)
    receiver_rows = sorted(receiver_velocity_rows, key=_time)
    raw_rows = sorted(raw_doppler_rows, key=_time)
    residual_sorted = sorted(residual_rows or [], key=_time)
    ci = fi = ri = rdi = resid_i = 0
    output: list[dict[str, Any]] = []
    for prior in sorted(prior_rows, key=_time):
        time_value = _time(prior)
        go2_vn = _f(prior.get("vn"), math.nan)
        go2_ve = _f(prior.get("ve"), math.nan)
        finite = math.isfinite(go2_vn) and math.isfinite(go2_ve)
        contact, ci, cdt = _nearest(contact_rows, time_value, ci, 0.55)
        frame, fi, fdt = _nearest(frame_rows, time_value, fi, 0.55)
        receiver, ri, rdt = _nearest(receiver_rows, time_value, ri, 0.25)
        raw, rdi, rawdt = _nearest(raw_rows, time_value, rdi, 0.25)
        residual, resid_i, resdt = _nearest(residual_sorted, time_value, resid_i, 0.55)
        contact_conf, contact_probability, mode, gait = _contact_confidence(contact)
        frame_conf, frame_diff = _frame_confidence(frame, frame_equivalence_report)
        receiver_diff = (
            _horizontal_diff(go2_vn, go2_ve, _f(receiver.get("vn"), math.nan), _f(receiver.get("ve"), math.nan))
            if receiver
            else math.nan
        )
        raw_diff = (
            _horizontal_diff(go2_vn, go2_ve, _f(raw.get("vn"), math.nan), _f(raw.get("ve"), math.nan))
            if raw
            else math.nan
        )
        receiver_conf = _consistency_from_diff(receiver_diff)
        raw_conf = _consistency_from_diff(raw_diff)
        cross_conf = max(receiver_conf, raw_conf) if receiver or raw else 0.40
        time_conf = _time_confidence(max(value for value in [cdt, fdt, rdt, rawdt] if math.isfinite(value)) if finite else math.inf)
        residual_conf, residual_norm, normalized_innovation = _residual_confidence(residual if resdt <= 0.55 else None)
        confidence = _clamp01(
            0.32 * cross_conf
            + 0.24 * frame_conf
            + 0.18 * time_conf
            + 0.16 * contact_conf
            + 0.10 * residual_conf
        )
        severe_time_mismatch = all(not math.isfinite(value) or value > 0.55 for value in [cdt, fdt, rdt, rawdt])
        valid = finite and not severe_time_mismatch
        level = _confidence_level(
            confidence=confidence,
            valid=valid,
            frame_confidence=frame_conf,
            time_confidence=time_conf,
            cross_confidence=cross_conf,
            contact_confidence=contact_conf,
        )
        if level == "invalid":
            confidence = min(confidence, 0.14)
        output.append(
            {
                "time": time_value,
                "vn": go2_vn if finite else "",
                "ve": go2_ve if finite else "",
                "vd": 0.0,
                "confidence": confidence,
                "confidence_level": level,
                "contact_confidence": contact_conf,
                "frame_confidence": frame_conf,
                "receiver_consistency_confidence": receiver_conf,
                "raw_doppler_consistency_confidence": raw_conf,
                "cross_source_consistency_confidence": cross_conf,
                "time_alignment_confidence": time_conf,
                "residual_consistency_confidence": residual_conf,
                "contact_probability": contact_probability if math.isfinite(contact_probability) else "",
                "frame_horizontal_difference_mps": frame_diff if math.isfinite(frame_diff) else "",
                "go2_minus_receiver_horizontal_mps": receiver_diff if math.isfinite(receiver_diff) else "",
                "go2_minus_raw_horizontal_mps": raw_diff if math.isfinite(raw_diff) else "",
                "source_aware_residual_norm": residual_norm if math.isfinite(residual_norm) else "",
                "source_aware_normalized_innovation": normalized_innovation if math.isfinite(normalized_innovation) else "",
                "mode": mode,
                "gait_type": gait,
                "reason_codes": _reason_codes(
                    level=level,
                    contact_confidence=contact_conf,
                    frame_confidence=frame_conf,
                    cross_confidence=cross_conf,
                    time_confidence=time_conf,
                    residual_confidence=residual_conf,
                    receiver_diff=receiver_diff if math.isfinite(receiver_diff) else None,
                    raw_diff=raw_diff if math.isfinite(raw_diff) else None,
                ),
                "no_truth_claim": True,
                "no_trace_tuning": True,
                "no_final_v23_tuning": True,
            }
        )
    counts = {level: sum(1 for row in output if row["confidence_level"] == level) for level in ["high", "medium", "low", "invalid"]}
    report = {
        "stage": "N7C4_go2_horizontal_velocity_strength_calibration",
        "policy_name": "n7c4_recalibrated_cross_source_confidence",
        "row_count": len(output),
        "confidence_counts": counts,
        "high_count_not_forced": True,
        "high_zero_explanation": "cross-source/frame/contact gates did not jointly pass high criteria" if counts["high"] == 0 else "",
        "confidence_combination": "bounded weighted cross-source/frame/time/contact/residual consistency",
        "uses_solver_visible_residuals_if_available": bool(residual_sorted),
        "uses_absolute_error": False,
        "navigation_metric_feedback_tuning": False,
        "no_artificial_balancing": True,
        "go2_velocity_truth_claim": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }
    return output, report


def write_recalibrated_confidence_outputs(
    *,
    output_dir: str | Path,
    confidence_rows: list[dict[str, Any]],
    confidence_report: dict[str, Any],
) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "GO2_HORIZONTAL_VELOCITY_RECALIBRATED_CONFIDENCE_TIMESERIES.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECALIBRATED_CONFIDENCE_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in RECALIBRATED_CONFIDENCE_FIELDS} for row in confidence_rows])
    report_path = out / "GO2_HORIZONTAL_VELOCITY_RECALIBRATED_CONFIDENCE_REPORT.json"
    report_path.write_text(json.dumps(confidence_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path
