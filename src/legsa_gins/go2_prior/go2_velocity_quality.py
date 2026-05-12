"""N7B Go2 velocity cross-source consistency diagnostics.

中文说明：这里比较 Go2 velocity、receiver-native velocity 和 raw Doppler
velocity 的一致性；它不是 truth error，N7B 不激活 Go2 velocity prior。
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values)) if all(math.isfinite(value) for value in values) else math.nan


def _time_value(row: dict[str, Any]) -> float:
    aligned = _f(row.get("aligned_time"))
    return aligned if math.isfinite(aligned) else _f(row.get("time"), 0.0)


def _rmse(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return math.sqrt(sum(value * value for value in finite) / len(finite)) if finite else None


def _mean(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return sum(finite) / len(finite) if finite else None


def _corr(a: list[float], b: list[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(a, b) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 2:
        return None
    xs, ys = zip(*pairs)
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in pairs)
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (den_x * den_y) if den_x and den_y else None


def _nearest_from_index(
    target_rows: list[dict[str, Any]],
    time_value: float,
    start_index: int,
    *,
    tolerance: float,
) -> tuple[dict[str, Any] | None, int]:
    if not target_rows or not math.isfinite(time_value):
        return None, start_index
    index = max(0, min(start_index, len(target_rows) - 1))
    while (
        index + 1 < len(target_rows)
        and abs(_f(target_rows[index + 1].get("time")) - time_value) <= abs(_f(target_rows[index].get("time")) - time_value)
    ):
        index += 1
    best = target_rows[index]
    return (best if abs(_f(best.get("time")) - time_value) <= tolerance else None), index


def _go2_velocity(row: dict[str, Any]) -> list[float]:
    return [_f(row.get(f"go2_velocity_{axis}")) for axis in range(3)]


def _source_velocity(row: dict[str, Any]) -> list[float]:
    return [_f(row.get(axis)) for axis in ["vn", "ve", "vd"]]


def _contact_by_time(contact_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(contact_rows, key=lambda row: _f(row.get("time"), 0.0))


def _contact_label(contact_rows: list[dict[str, Any]], time_value: float, start_index: int) -> tuple[str, int]:
    row, index = _nearest_from_index(contact_rows, time_value, start_index, tolerance=0.10)
    return (str(row.get("contact_label", "unknown")) if row else "unknown"), index


def _conditioned_stats(timeseries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in timeseries:
        buckets[str(row.get("contact_label", "unknown"))].append(_f(row.get("go2_speed_norm")))
    return {
        label: {"count": len(values), "mean_go2_speed_norm": _mean(values), "rmse_go2_speed_norm": _rmse(values)}
        for label, values in sorted(buckets.items())
    }


def _standing_moving_consistency(timeseries: list[dict[str, Any]]) -> dict[str, Any]:
    standing = [_f(row.get("go2_speed_norm")) for row in timeseries if row.get("contact_label") == "standing_contact"]
    moving = [_f(row.get("go2_speed_norm")) for row in timeseries if row.get("contact_label") == "walking_contact"]
    standing_mean = _mean(standing)
    moving_mean = _mean(moving)
    status = "insufficient_contact_conditioning"
    if standing_mean is not None and moving_mean is not None:
        status = "consistent" if standing_mean <= max(0.25, moving_mean * 0.75) else "review"
    return {
        "standing_mean_go2_speed_norm": standing_mean,
        "moving_mean_go2_speed_norm": moving_mean,
        "status": status,
    }


def analyze_velocity_quality(
    go2_rows: list[dict[str, Any]],
    *,
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    contact_rows: list[dict[str, Any]],
    tolerance: float = 0.55,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    receiver_rows = sorted(receiver_velocity_rows, key=lambda row: _f(row.get("time"), 0.0))
    raw_rows = sorted(raw_doppler_rows, key=lambda row: _f(row.get("time"), 0.0))
    contact_sorted = _contact_by_time(contact_rows)
    timeseries: list[dict[str, Any]] = []
    receiver_diff_norms: list[float] = []
    raw_diff_norms: list[float] = []
    receiver_go2_norms: list[float] = []
    receiver_source_norms: list[float] = []
    raw_go2_norms: list[float] = []
    raw_source_norms: list[float] = []
    receiver_component_diffs = [[], [], []]
    raw_component_diffs = [[], [], []]
    receiver_index = 0
    raw_index = 0
    contact_index = 0
    for row in sorted(go2_rows, key=_time_value):
        time_value = _time_value(row)
        go2 = _go2_velocity(row)
        if not all(math.isfinite(value) for value in go2):
            continue
        go2_norm = _norm(go2)
        receiver, receiver_index = _nearest_from_index(receiver_rows, time_value, receiver_index, tolerance=tolerance)
        raw, raw_index = _nearest_from_index(raw_rows, time_value, raw_index, tolerance=tolerance)
        receiver_velocity = _source_velocity(receiver) if receiver else [math.nan, math.nan, math.nan]
        raw_velocity = _source_velocity(raw) if raw else [math.nan, math.nan, math.nan]
        receiver_diff = [go2[axis] - receiver_velocity[axis] for axis in range(3)]
        raw_diff = [go2[axis] - raw_velocity[axis] for axis in range(3)]
        receiver_diff_norm = _norm(receiver_diff)
        raw_diff_norm = _norm(raw_diff)
        if math.isfinite(receiver_diff_norm):
            receiver_diff_norms.append(receiver_diff_norm)
            receiver_go2_norms.append(go2_norm)
            receiver_source_norms.append(_norm(receiver_velocity))
            for axis in range(3):
                receiver_component_diffs[axis].append(receiver_diff[axis])
        if math.isfinite(raw_diff_norm):
            raw_diff_norms.append(raw_diff_norm)
            raw_go2_norms.append(go2_norm)
            raw_source_norms.append(_norm(raw_velocity))
            for axis in range(3):
                raw_component_diffs[axis].append(raw_diff[axis])
        contact_label, contact_index = _contact_label(contact_sorted, time_value, contact_index)
        timeseries.append(
            {
                "time": time_value,
                "go2_v0": go2[0],
                "go2_v1": go2[1],
                "go2_v2": go2[2],
                "go2_speed_norm": go2_norm,
                "receiver_vn": receiver_velocity[0] if math.isfinite(receiver_velocity[0]) else "",
                "receiver_ve": receiver_velocity[1] if math.isfinite(receiver_velocity[1]) else "",
                "receiver_vd": receiver_velocity[2] if math.isfinite(receiver_velocity[2]) else "",
                "receiver_speed_norm": _norm(receiver_velocity) if math.isfinite(_norm(receiver_velocity)) else "",
                "raw_vn": raw_velocity[0] if math.isfinite(raw_velocity[0]) else "",
                "raw_ve": raw_velocity[1] if math.isfinite(raw_velocity[1]) else "",
                "raw_vd": raw_velocity[2] if math.isfinite(raw_velocity[2]) else "",
                "raw_speed_norm": _norm(raw_velocity) if math.isfinite(_norm(raw_velocity)) else "",
                "go2_minus_receiver_velocity_norm": receiver_diff_norm if math.isfinite(receiver_diff_norm) else "",
                "go2_minus_raw_doppler_velocity_norm": raw_diff_norm if math.isfinite(raw_diff_norm) else "",
                "contact_label": contact_label,
                "not_truth": True,
                "go2_velocity_prior_enabled": False,
            }
        )
    receiver_rmse = _rmse(receiver_diff_norms)
    raw_rmse = _rmse(raw_diff_norms)
    receiver_corr = _corr(receiver_go2_norms, receiver_source_norms)
    raw_corr = _corr(raw_go2_norms, raw_source_norms)
    aligned_receiver = len(receiver_diff_norms)
    aligned_raw = len(raw_diff_norms)
    consistency_status = "insufficient_cross_source_data"
    if aligned_receiver >= 10 or aligned_raw >= 10:
        worst_rmse = max(value for value in [receiver_rmse, raw_rmse] if value is not None)
        best_corr = max(value for value in [receiver_corr, raw_corr] if value is not None) if any(
            value is not None for value in [receiver_corr, raw_corr]
        ) else None
        if worst_rmse > 3.0 and (best_corr is None or best_corr < 0.35):
            consistency_status = "strongly_inconsistent"
        elif worst_rmse <= 1.25 or (best_corr is not None and best_corr >= 0.70):
            consistency_status = "acceptable_for_future_review"
        else:
            consistency_status = "review_required"
    recommendation = "conditional" if consistency_status == "acceptable_for_future_review" else "false"
    report: dict[str, Any] = {
        "stage": "N7B_go2_velocity_contact_readiness",
        "aligned_count_to_receiver_velocity": aligned_receiver,
        "aligned_count_to_raw_doppler": aligned_raw,
        "velocity_diff_rmse_to_receiver": receiver_rmse,
        "velocity_diff_rmse_to_raw": raw_rmse,
        "bias_body_or_ned": {
            "to_receiver": {
                "axis_0": _mean(receiver_component_diffs[0]),
                "axis_1": _mean(receiver_component_diffs[1]),
                "axis_2": _mean(receiver_component_diffs[2]),
            },
            "to_raw_doppler": {
                "axis_0": _mean(raw_component_diffs[0]),
                "axis_1": _mean(raw_component_diffs[1]),
                "axis_2": _mean(raw_component_diffs[2]),
            },
        },
        "bias_n": _mean(receiver_component_diffs[0]),
        "bias_e": _mean(receiver_component_diffs[1]),
        "bias_d": _mean(receiver_component_diffs[2]),
        "correlation": {
            "go2_norm_vs_receiver_norm": receiver_corr,
            "go2_norm_vs_raw_doppler_norm": raw_corr,
        },
        "contact_conditioned_velocity_stats": _conditioned_stats(timeseries),
        "moving_vs_standing_velocity_consistency": _standing_moving_consistency(timeseries),
        "consistency_status": consistency_status,
        "velocity_prior_activation_recommended": recommendation,
        "cross_source_consistency_not_truth_error": True,
        "not_truth": True,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    return timeseries, report


def write_velocity_quality_outputs(
    go2_rows: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    contact_rows: list[dict[str, Any]],
) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timeseries, report = analyze_velocity_quality(
        go2_rows,
        receiver_velocity_rows=receiver_velocity_rows,
        raw_doppler_rows=raw_doppler_rows,
        contact_rows=contact_rows,
    )
    csv_path = out / "GO2_VELOCITY_QUALITY_TIMESERIES.csv"
    fieldnames = list(timeseries[0].keys()) if timeseries else [
        "time",
        "go2_speed_norm",
        "not_truth",
        "go2_velocity_prior_enabled",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timeseries)
    report_path = out / "GO2_VELOCITY_QUALITY_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, timeseries, report
