"""N7C3 confidence model for bounded Go2 horizontal velocity priors.

中文说明：confidence 只来自 solver-visible / Go2-visible evidence：N7B4
contact probability、N7B5 frame equivalence、receiver/raw cross-source
consistency、mode/gait/body motion、time alignment。它不是 truth label，
不读取 trace/final_v23 output，也不使用导航指标反馈调参。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


CONFIDENCE_FIELDS = [
    "time",
    "vn",
    "ve",
    "vd",
    "confidence",
    "confidence_level",
    "contact_confidence",
    "frame_confidence",
    "cross_source_consistency_confidence",
    "motion_state_confidence",
    "time_alignment_confidence",
    "contact_probability",
    "frame_horizontal_difference_mps",
    "go2_minus_receiver_horizontal_mps",
    "go2_minus_raw_horizontal_mps",
    "mode",
    "gait_type",
    "reason_codes",
    "no_truth_claim",
    "no_trace_tuning",
    "no_final_v23_tuning",
]


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv_rows(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fieldnames} for row in rows])
    return output


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


def _clamp01(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _time(row: dict[str, Any]) -> float:
    return _f(row.get("time"), 0.0)


def _nearest(
    rows: list[dict[str, Any]],
    time_value: float,
    start_index: int,
    *,
    tolerance: float,
) -> tuple[dict[str, Any] | None, int, float]:
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


def _confidence_from_diff(diff_mps: float | None) -> float:
    if diff_mps is None or not math.isfinite(diff_mps):
        return 0.55
    if diff_mps <= 0.75:
        return 1.0
    if diff_mps <= 1.50:
        return 0.75
    if diff_mps <= 2.50:
        return 0.45
    if diff_mps <= 5.00:
        return 0.20
    return 0.05


def _confidence_from_time(max_dt: float) -> float:
    if not math.isfinite(max_dt):
        return 0.45
    if max_dt <= 0.05:
        return 1.0
    if max_dt <= 0.10:
        return 0.85
    if max_dt <= 0.25:
        return 0.60
    if max_dt <= 0.55:
        return 0.35
    return 0.10


def _confidence_level(confidence: float) -> str:
    if confidence >= 0.80:
        return "high"
    if confidence >= 0.60:
        return "medium"
    if confidence >= 0.15:
        return "low"
    return "invalid"


def _harmonic(values: dict[str, float], weights: dict[str, float]) -> float:
    numerator = 0.0
    denominator = 0.0
    for key, weight in weights.items():
        value = max(1.0e-3, _clamp01(values.get(key, 0.0)))
        numerator += weight
        denominator += weight / value
    return numerator / denominator if denominator else 0.0


def _conservative_combine(components: dict[str, float]) -> float:
    weights = {
        "contact_confidence": 0.30,
        "frame_confidence": 0.25,
        "cross_source_consistency_confidence": 0.25,
        "motion_state_confidence": 0.10,
        "time_alignment_confidence": 0.10,
    }
    harmonic = _harmonic(components, weights)
    minimum = min(_clamp01(value) for value in components.values()) if components else 0.0
    return _clamp01(0.70 * harmonic + 0.30 * minimum)


def _contact_rows_for_selected_model(rows: list[dict[str, Any]], report: dict[str, Any]) -> list[dict[str, Any]]:
    selected = str(report.get("selected_contact_probability_model") or "")
    if selected:
        filtered = [row for row in rows if str(row.get("model_id") or "") == selected]
        if filtered:
            return sorted(filtered, key=_time)
    return sorted(rows, key=_time)


def _contact_confidence(row: dict[str, Any] | None) -> float:
    if not row:
        return 0.35
    support = _clamp01(_f(row.get("support_probability"), 0.0))
    confidence_score = _clamp01(_f(row.get("confidence_score"), 0.0))
    uncertainty = _clamp01(_f(row.get("uncertainty_probability"), 0.5))
    # Contact probability should act conservatively: support, feature confidence,
    # and uncertainty penalty all matter; no single feature can dominate.
    return _clamp01(min(support, 0.75 * confidence_score + 0.25 * support) * (1.0 - 0.35 * uncertainty))


def _frame_confidence(row: dict[str, Any] | None, frame_report: dict[str, Any]) -> float:
    base = 0.65 if frame_report.get("frame_equivalent_for_horizontal_only") else 0.50
    if not row:
        return base
    hdiff = _f(row.get("horizontal_difference_mps"), math.nan)
    angle = abs(_f(row.get("horizontal_angle_difference_deg"), math.nan))
    diff_score = 1.0 - min(1.0, hdiff / 1.0) if math.isfinite(hdiff) else base
    angle_score = 1.0 - min(1.0, angle / 20.0) if math.isfinite(angle) else base
    return _clamp01(min(max(base, 0.35), 0.55 * diff_score + 0.45 * angle_score))


def _motion_confidence(prior: dict[str, Any], contact: dict[str, Any] | None) -> float:
    vn = _f(prior.get("vn"), 0.0)
    ve = _f(prior.get("ve"), 0.0)
    speed = math.hypot(vn, ve)
    mode = str((contact or {}).get("mode") or prior.get("mode") or "").lower()
    gait = str((contact or {}).get("gait_type") or prior.get("gait_type") or "").lower()
    if speed <= 2.50:
        speed_score = 0.95
    elif speed <= 3.70:
        speed_score = 0.80
    elif speed <= 5.00:
        speed_score = 0.55
    else:
        speed_score = 0.10
    mode_score = 0.80
    if "stand" in mode or "idle" in mode or "stand" in gait:
        mode_score = 0.90
    elif "walk" in mode or "trot" in gait or "run" in gait:
        mode_score = 0.78
    return _clamp01(min(speed_score, mode_score))


def _reason_codes(
    *,
    components: dict[str, float],
    confidence: float,
    go2_speed_mps: float,
    receiver_diff: float | None,
    raw_diff: float | None,
) -> list[str]:
    reasons: list[str] = []
    if components["contact_confidence"] < 0.35:
        reasons.append("low_contact_probability")
    if components["frame_confidence"] < 0.45:
        reasons.append("frame_equivalence_weak")
    if components["cross_source_consistency_confidence"] < 0.45:
        reasons.append("cross_source_consistency_weak")
    if components["time_alignment_confidence"] < 0.45:
        reasons.append("time_alignment_weak")
    if go2_speed_mps > 5.0:
        reasons.append("go2_speed_exceeds_diagnostic_limit")
    if receiver_diff is None and raw_diff is None:
        reasons.append("cross_source_rows_missing")
    if confidence < 0.15:
        reasons.append("invalid_confidence_hard_skip")
    if not reasons:
        reasons.append("bounded_soft_gate_nominal")
    reasons.extend(["no_trace_tuning", "no_final_v23_tuning", "go2_velocity_not_truth"])
    return reasons


def build_go2_horizontal_velocity_confidence(
    *,
    prior_rows: list[dict[str, Any]],
    contact_probability_rows: list[dict[str, Any]],
    contact_probability_report: dict[str, Any],
    frame_equivalence_rows: list[dict[str, Any]],
    frame_equivalence_report: dict[str, Any],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build bounded confidence rows for N7C3 adaptive std."""

    contact_rows = _contact_rows_for_selected_model(contact_probability_rows, contact_probability_report)
    frame_rows = sorted(frame_equivalence_rows, key=_time)
    receiver_rows = sorted(receiver_velocity_rows, key=_time)
    raw_rows = sorted(raw_doppler_rows, key=_time)
    ci = fi = ri = rdi = 0
    confidence_rows: list[dict[str, Any]] = []
    for prior in sorted(prior_rows, key=_time):
        time_value = _time(prior)
        contact, ci, contact_dt = _nearest(contact_rows, time_value, ci, tolerance=0.25)
        frame, fi, frame_dt = _nearest(frame_rows, time_value, fi, tolerance=0.25)
        receiver, ri, receiver_dt = _nearest(receiver_rows, time_value, ri, tolerance=0.55)
        raw, rdi, raw_dt = _nearest(raw_rows, time_value, rdi, tolerance=0.55)
        vn = _f(prior.get("vn"), 0.0)
        ve = _f(prior.get("ve"), 0.0)
        receiver_diff = (
            _horizontal_diff(vn, ve, _f(receiver.get("vn")), _f(receiver.get("ve"))) if receiver else None
        )
        raw_diff = _horizontal_diff(vn, ve, _f(raw.get("vn")), _f(raw.get("ve"))) if raw else None
        source_scores = [_confidence_from_diff(value) for value in [receiver_diff, raw_diff] if value is not None]
        cross_source = min(source_scores) if source_scores else 0.55
        max_dt = max(
            value
            for value in [contact_dt, frame_dt, receiver_dt if receiver else math.nan, raw_dt if raw else math.nan]
            if math.isfinite(value)
        ) if any(math.isfinite(value) for value in [contact_dt, frame_dt, receiver_dt, raw_dt]) else math.inf
        components = {
            "contact_confidence": _contact_confidence(contact),
            "frame_confidence": _frame_confidence(frame, frame_equivalence_report),
            "cross_source_consistency_confidence": cross_source,
            "motion_state_confidence": _motion_confidence(prior, contact),
            "time_alignment_confidence": _confidence_from_time(max_dt),
        }
        confidence = _conservative_combine(components)
        go2_speed = math.hypot(vn, ve)
        reasons = _reason_codes(
            components=components,
            confidence=confidence,
            go2_speed_mps=go2_speed,
            receiver_diff=receiver_diff,
            raw_diff=raw_diff,
        )
        confidence_rows.append(
            {
                "time": time_value,
                "vn": vn,
                "ve": ve,
                "vd": _f(prior.get("vd"), 0.0),
                "confidence": confidence,
                "confidence_level": _confidence_level(confidence),
                "contact_confidence": components["contact_confidence"],
                "frame_confidence": components["frame_confidence"],
                "cross_source_consistency_confidence": components["cross_source_consistency_confidence"],
                "motion_state_confidence": components["motion_state_confidence"],
                "time_alignment_confidence": components["time_alignment_confidence"],
                "contact_probability": _f((contact or {}).get("support_probability"), math.nan),
                "frame_horizontal_difference_mps": _f((frame or {}).get("horizontal_difference_mps"), math.nan),
                "go2_minus_receiver_horizontal_mps": receiver_diff if receiver_diff is not None else "",
                "go2_minus_raw_horizontal_mps": raw_diff if raw_diff is not None else "",
                "mode": (contact or {}).get("mode", prior.get("mode", "")),
                "gait_type": (contact or {}).get("gait_type", prior.get("gait_type", "")),
                "reason_codes": ";".join(reasons),
                "no_truth_claim": True,
                "no_trace_tuning": True,
                "no_final_v23_tuning": True,
            }
        )
    counts = {level: sum(1 for row in confidence_rows if row["confidence_level"] == level) for level in ["high", "medium", "low", "invalid"]}
    values = sorted(float(row["confidence"]) for row in confidence_rows)
    p50 = values[len(values) // 2] if values else 0.0
    p95 = values[min(len(values) - 1, int(0.95 * (len(values) - 1)))] if values else 0.0
    report = {
        "stage": "N7C3_go2_horizontal_velocity_bounded_adaptive_std",
        "confidence_policy": "weighted_conservative_harmonic_mean_with_min_guard",
        "confidence_components": [
            "contact_confidence",
            "frame_confidence",
            "cross_source_consistency_confidence",
            "motion_state_confidence",
            "time_alignment_confidence",
        ],
        "row_count": len(confidence_rows),
        "confidence_counts": counts,
        "confidence_p50": p50,
        "confidence_p95": p95,
        "confidence_min": values[0] if values else 0.0,
        "confidence_max": values[-1] if values else 0.0,
        "selected_contact_probability_model": contact_probability_report.get("selected_contact_probability_model", ""),
        "frame_equivalence_source": "N7B5_GO2_FRAME_EQUIVALENCE_TIMESERIES",
        "cross_source_consistency_not_truth_error": True,
        "no_truth_claim": True,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "navigation_metric_feedback_tuning": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    return confidence_rows, report


def write_go2_horizontal_velocity_confidence_outputs(
    *,
    output_dir: str | Path,
    confidence_rows: list[dict[str, Any]],
    confidence_report: dict[str, Any],
) -> tuple[Path, Path]:
    out = Path(output_dir)
    csv_path = write_csv_rows(out / "GO2_HORIZONTAL_VELOCITY_CONFIDENCE_TIMESERIES.csv", confidence_rows, CONFIDENCE_FIELDS)
    report_path = write_json(out / "GO2_HORIZONTAL_VELOCITY_CONFIDENCE_REPORT.json", confidence_report)
    return csv_path, report_path
