"""N7B Go2 yaw-rate readiness diagnostics.

中文说明：yaw_speed 与 Go2 yaw 导数只做内部一致性检查，不激活 yaw prior。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .go2_contact_state import _f
from .go2_velocity_quality import _corr, _rmse


def _time_value(row: dict[str, Any]) -> float:
    aligned = _f(row.get("aligned_time"))
    return aligned if math.isfinite(aligned) else _f(row.get("time"), 0.0)


def _unwrap(yaws: list[float]) -> list[float]:
    if not yaws:
        return []
    out = [yaws[0]]
    for value in yaws[1:]:
        previous = out[-1]
        delta = value - previous
        while delta > math.pi:
            value -= 2.0 * math.pi
            delta = value - previous
        while delta < -math.pi:
            value += 2.0 * math.pi
            delta = value - previous
        out.append(value)
    return out


def analyze_yaw_rate_readiness(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered = sorted(rows, key=_time_value)
    times = [_time_value(row) for row in ordered]
    yaws = [_f(row.get("yaw_rad")) for row in ordered]
    yaw_speeds = [_f(row.get("yaw_speed_radps")) for row in ordered]
    unwrapped = _unwrap(yaws)
    derivatives: list[float] = [math.nan for _ in ordered]
    for index in range(1, len(ordered)):
        dt = times[index] - times[index - 1]
        if dt > 0.0 and math.isfinite(unwrapped[index]) and math.isfinite(unwrapped[index - 1]):
            derivatives[index] = (unwrapped[index] - unwrapped[index - 1]) / dt
    diffs = [speed - deriv for speed, deriv in zip(yaw_speeds, derivatives) if math.isfinite(speed) and math.isfinite(deriv)]
    available_count = sum(1 for value in yaw_speeds if math.isfinite(value))
    rmse = _rmse(diffs)
    corr = _corr(yaw_speeds, derivatives)
    if available_count < 10 or len(diffs) < 10:
        status = "insufficient_yaw_speed_data"
    elif rmse is not None and (rmse <= 0.05 or (rmse <= 0.20 and (corr is None or corr >= 0.65))):
        status = "stable_for_future_review"
    elif rmse is not None and rmse <= 0.50:
        status = "review_required"
    else:
        status = "inconsistent"
    timeseries = [
        {
            "time": time_value,
            "go2_yaw_rad": yaw,
            "go2_yaw_speed_radps": speed if math.isfinite(speed) else "",
            "go2_yaw_derivative_radps": deriv if math.isfinite(deriv) else "",
            "yaw_speed_minus_derivative": (speed - deriv) if math.isfinite(speed) and math.isfinite(deriv) else "",
            "not_truth": True,
            "go2_yaw_prior_enabled": False,
        }
        for time_value, yaw, speed, deriv in zip(times, yaws, yaw_speeds, derivatives)
    ]
    report: dict[str, Any] = {
        "stage": "N7B_go2_velocity_contact_readiness",
        "yaw_speed_available": available_count > 0,
        "yaw_speed_available_count": available_count,
        "yaw_derivative_aligned_count": len(diffs),
        "yaw_speed_vs_go2_yaw_derivative_rmse": rmse,
        "yaw_speed_vs_go2_yaw_derivative_bias": (sum(diffs) / len(diffs) if diffs else None),
        "correlation": corr,
        "consistency_status": status,
        "yaw_rate_prior_recommended": "conditional" if status == "stable_for_future_review" else "false",
        "go2_yaw_prior_enabled": False,
        "not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    return timeseries, report


def write_yaw_rate_readiness_outputs(rows: list[dict[str, Any]], output_dir: str | Path) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timeseries, report = analyze_yaw_rate_readiness(rows)
    csv_path = out / "GO2_YAW_RATE_READINESS_TIMESERIES.csv"
    fieldnames = list(timeseries[0].keys()) if timeseries else ["time", "go2_yaw_speed_radps", "go2_yaw_prior_enabled"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timeseries)
    report_path = out / "GO2_YAW_RATE_READINESS_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, timeseries, report
