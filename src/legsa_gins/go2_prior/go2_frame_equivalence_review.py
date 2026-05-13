"""N7B5 Go2 top-frame equivalence review.

中文说明：N7B5 只比较 N7B4 top frame candidates 是否在 horizontal velocity
上近似等价；receiver/raw Doppler 只作 cross-source consistency，不是 truth。
不使用 trace 或 final_v23 output 做 frame 选择或阈值调整。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _time_value
from .go2_velocity_frame_internal_external_score import _candidate_velocity
from .go2_velocity_quality import _nearest_from_index


DEFAULT_PRIMARY_FRAME = "go2_velocity_as_body_flu_then_rotate_by_go2_attitude"
DEFAULT_SECONDARY_FRAME = "yaw_only_rotation_diagnostic_only"


def _rmse(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return None
    return math.sqrt(sum(value * value for value in finite) / len(finite))


def _percentile(values: list[float], q: float) -> float | None:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return None
    index = max(0, min(len(finite) - 1, int(round(q * (len(finite) - 1)))))
    return finite[index]


def _horizontal_angle_deg(a: list[float], b: list[float]) -> float:
    an = math.hypot(a[0], a[1])
    bn = math.hypot(b[0], b[1])
    if an <= 1.0e-6 or bn <= 1.0e-6:
        return math.nan
    cosine = max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / (an * bn)))
    return math.degrees(math.acos(cosine))


def _segments(row: dict[str, Any]) -> list[str]:
    yaw_rate = abs(_f(row.get("yaw_speed_radps"), 0.0))
    roll_pitch = max(abs(_f(row.get("roll_rad"), 0.0)), abs(_f(row.get("pitch_rad"), 0.0)))
    labels: list[str] = []
    if yaw_rate < 0.05 and roll_pitch < 0.06:
        labels.append("straight")
    if yaw_rate >= 0.08:
        labels.append("turning")
    if roll_pitch >= 0.08:
        labels.append("high_roll_pitch")
    if yaw_rate >= 0.18:
        labels.append("high_yaw_rate")
    return labels or ["nominal"]


def _source_velocity(row: dict[str, Any] | None) -> list[float]:
    if not row:
        return [math.nan, math.nan, math.nan]
    return [_f(row.get(axis)) for axis in ("vn", "ve", "vd")]


def _source_consistency(
    *,
    go2_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    frame_name: str,
    tolerance: float = 0.55,
) -> dict[str, Any]:
    source_sorted = sorted(source_rows, key=lambda row: _f(row.get("time"), 0.0))
    source_index = 0
    full_diffs: list[float] = []
    horizontal_diffs: list[float] = []
    for row in sorted(go2_rows, key=_time_value):
        candidate = _candidate_velocity(row, frame_name)
        if not all(math.isfinite(value) for value in candidate):
            continue
        source, source_index = _nearest_from_index(source_sorted, _time_value(row), source_index, tolerance=tolerance)
        svel = _source_velocity(source)
        if not all(math.isfinite(value) for value in svel):
            continue
        full_diffs.append(math.sqrt(sum((candidate[index] - svel[index]) ** 2 for index in range(3))))
        horizontal_diffs.append(math.hypot(candidate[0] - svel[0], candidate[1] - svel[1]))
    return {
        "aligned_count": len(full_diffs),
        "full_rmse": _rmse(full_diffs),
        "horizontal_rmse": _rmse(horizontal_diffs),
    }


def review_frame_equivalence(
    *,
    go2_rows: list[dict[str, Any]],
    frame_score_report: dict[str, Any],
    receiver_velocity_rows: list[dict[str, Any]] | None = None,
    raw_doppler_rows: list[dict[str, Any]] | None = None,
    primary_frame: str | None = None,
    secondary_frame: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compare top N7B4 frame candidates for horizontal-only diagnostic use."""

    primary = primary_frame or str(frame_score_report.get("best_candidate") or DEFAULT_PRIMARY_FRAME)
    secondary = (
        secondary_frame
        or str(frame_score_report.get("second_best") or frame_score_report.get("top2_frame_for_diagnostic") or DEFAULT_SECONDARY_FRAME)
    )
    timeseries: list[dict[str, Any]] = []
    horizontal_diffs: list[float] = []
    vertical_diffs: list[float] = []
    angles: list[float] = []
    segment_values: dict[str, dict[str, list[float]]] = {
        "straight": {"horizontal": [], "vertical": [], "angle": []},
        "turning": {"horizontal": [], "vertical": [], "angle": []},
        "high_roll_pitch": {"horizontal": [], "vertical": [], "angle": []},
        "high_yaw_rate": {"horizontal": [], "vertical": [], "angle": []},
        "nominal": {"horizontal": [], "vertical": [], "angle": []},
    }
    for row in sorted(go2_rows, key=_time_value):
        first = _candidate_velocity(row, primary)
        second = _candidate_velocity(row, secondary)
        if not all(math.isfinite(value) for value in [*first, *second]):
            continue
        dh = math.hypot(first[0] - second[0], first[1] - second[1])
        dv = abs(first[2] - second[2])
        angle = _horizontal_angle_deg(first, second)
        horizontal_diffs.append(dh)
        vertical_diffs.append(dv)
        if math.isfinite(angle):
            angles.append(angle)
        labels = _segments(row)
        for label in labels:
            segment_values.setdefault(label, {"horizontal": [], "vertical": [], "angle": []})
            segment_values[label]["horizontal"].append(dh)
            segment_values[label]["vertical"].append(dv)
            if math.isfinite(angle):
                segment_values[label]["angle"].append(angle)
        timeseries.append(
            {
                "time": _time_value(row),
                "primary_frame": primary,
                "secondary_frame": secondary,
                "primary_vn": first[0],
                "primary_ve": first[1],
                "primary_vd": first[2],
                "secondary_vn": second[0],
                "secondary_ve": second[1],
                "secondary_vd": second[2],
                "horizontal_difference_mps": dh,
                "vertical_difference_mps": dv,
                "horizontal_angle_difference_deg": angle,
                "segment_labels": ";".join(labels),
                "diagnostic_only": True,
                "go2_velocity_truth_claim": False,
            }
        )
    horizontal_rmse = _rmse(horizontal_diffs)
    vertical_rmse = _rmse(vertical_diffs)
    angle_p95 = _percentile(angles, 0.95)
    segment_report = {
        label: {
            "count": len(values["horizontal"]),
            "horizontal_difference_rmse": _rmse(values["horizontal"]),
            "vertical_difference_rmse": _rmse(values["vertical"]),
            "horizontal_angle_p95_deg": _percentile(values["angle"], 0.95),
        }
        for label, values in segment_values.items()
    }
    equivalent = bool(
        timeseries
        and horizontal_rmse is not None
        and horizontal_rmse <= 0.20
        and (angle_p95 is None or angle_p95 <= 5.0)
    )
    vertical_ambiguous = bool(
        vertical_rmse is not None
        and horizontal_rmse is not None
        and (vertical_rmse >= 0.20 or vertical_rmse > max(0.05, 1.5 * horizontal_rmse))
    )
    receiver_rows = receiver_velocity_rows or []
    raw_rows = raw_doppler_rows or []
    source_consistency = {
        primary: {
            "receiver": _source_consistency(go2_rows=go2_rows, source_rows=receiver_rows, frame_name=primary),
            "raw_doppler": _source_consistency(go2_rows=go2_rows, source_rows=raw_rows, frame_name=primary),
        },
        secondary: {
            "receiver": _source_consistency(go2_rows=go2_rows, source_rows=receiver_rows, frame_name=secondary),
            "raw_doppler": _source_consistency(go2_rows=go2_rows, source_rows=raw_rows, frame_name=secondary),
        },
    }
    if not timeseries:
        policy = "do_not_use_go2_velocity"
    elif equivalent:
        policy = "use_best_frame_horizontal_only"
    else:
        primary_rmse = _f(source_consistency[primary]["receiver"].get("horizontal_rmse"))
        secondary_rmse = _f(source_consistency[secondary]["receiver"].get("horizontal_rmse"))
        policy = "use_best_frame_horizontal_only" if primary_rmse <= secondary_rmse else "use_yaw_only_horizontal_only"
    report = {
        "stage": "N7B5_go2_velocity_frame_horizontal_diagnostic",
        "primary_frame": primary,
        "secondary_frame": secondary,
        "frame_score_margin": frame_score_report.get("margin"),
        "frame_score_status": frame_score_report.get("frame_status"),
        "sample_count": len(timeseries),
        "top_candidate_difference": {
            "horizontal_rmse_mps": horizontal_rmse,
            "horizontal_p95_mps": _percentile(horizontal_diffs, 0.95),
            "vertical_rmse_mps": vertical_rmse,
            "vertical_p95_mps": _percentile(vertical_diffs, 0.95),
            "horizontal_angle_p50_deg": _percentile(angles, 0.50),
            "horizontal_angle_p95_deg": angle_p95,
        },
        "per_segment_difference": segment_report,
        "source_consistency_not_truth": source_consistency,
        "frame_equivalent_for_horizontal_only": equivalent,
        "vertical_component_ambiguous": vertical_ambiguous,
        "recommended_horizontal_policy": policy,
        "no_truth_claim": True,
        "diagnostic_only": True,
        "formal_go2_velocity_prior": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_frame_tuning": False,
        "final_v23_frame_tuning": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    return timeseries, report


def write_frame_equivalence_review(
    *,
    go2_rows: list[dict[str, Any]],
    frame_score_report: dict[str, Any],
    receiver_velocity_rows: list[dict[str, Any]] | None,
    raw_doppler_rows: list[dict[str, Any]] | None,
    output_dir: str | Path,
) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timeseries, report = review_frame_equivalence(
        go2_rows=go2_rows,
        frame_score_report=frame_score_report,
        receiver_velocity_rows=receiver_velocity_rows,
        raw_doppler_rows=raw_doppler_rows,
    )
    csv_path = out / "GO2_FRAME_EQUIVALENCE_TIMESERIES.csv"
    fieldnames = list(timeseries[0].keys()) if timeseries else [
        "time",
        "primary_frame",
        "secondary_frame",
        "horizontal_difference_mps",
        "vertical_difference_mps",
        "horizontal_angle_difference_deg",
        "diagnostic_only",
        "go2_velocity_truth_claim",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timeseries)
    report_path = out / "GO2_FRAME_EQUIVALENCE_REVIEW_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, timeseries, report
