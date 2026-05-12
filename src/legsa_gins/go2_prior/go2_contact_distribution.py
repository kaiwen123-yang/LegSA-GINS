"""N7B2 Go2 contact-field distribution review.

中文说明：本模块只统计 Go2 自身 foot_force、foot_speed、mode/gait/body_height
和 velocity norm 分布，用于 contact threshold readiness；不读取 trace 或
final_v23 output，也不激活 solver prior。
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _foot_speed_norm, _walking_hint, _standing_hint


def percentile(values: list[float], q: float) -> float | None:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return None
    index = max(0, min(len(finite) - 1, round((q / 100.0) * (len(finite) - 1))))
    return finite[index]


def _stats(values: list[float]) -> dict[str, float | None]:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return {key: None for key in ["min", "p10", "p25", "p35", "p50", "p75", "p95", "max", "mean"]}
    return {
        "min": min(finite),
        "p10": percentile(finite, 10),
        "p25": percentile(finite, 25),
        "p35": percentile(finite, 35),
        "p50": percentile(finite, 50),
        "p75": percentile(finite, 75),
        "p95": percentile(finite, 95),
        "max": max(finite),
        "mean": sum(finite) / len(finite),
    }


def _histogram(values: list[float], *, bins: int = 12) -> list[dict[str, float | int]]:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return []
    lo = min(finite)
    hi = max(finite)
    if hi <= lo:
        return [{"start": lo, "end": hi, "count": len(finite)}]
    width = (hi - lo) / bins
    counts = [0 for _ in range(bins)]
    for value in finite:
        index = min(bins - 1, int((value - lo) / width))
        counts[index] += 1
    return [{"start": lo + index * width, "end": lo + (index + 1) * width, "count": count} for index, count in enumerate(counts)]


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


def velocity_norm(row: dict[str, Any]) -> float:
    values = [_f(row.get(f"go2_velocity_{axis}")) for axis in range(3)]
    return math.sqrt(sum(value * value for value in values)) if all(math.isfinite(value) for value in values) else math.nan


def mode_gait_bucket(row: dict[str, Any]) -> str:
    if _standing_hint(row):
        return "standing_hint"
    if _walking_hint(row):
        return "walking_hint"
    speed = velocity_norm(row)
    if math.isfinite(speed) and speed < 0.15:
        return "low_speed_hint"
    return "unknown"


def analyze_contact_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    force_by_foot: dict[str, list[float]] = {f"foot_{foot}": [] for foot in range(4)}
    speed_by_foot: dict[str, list[float]] = {f"foot_{foot}": [] for foot in range(4)}
    force_speed_pairs_by_foot: dict[str, tuple[list[float], list[float]]] = {
        f"foot_{foot}": ([], []) for foot in range(4)
    }
    grouped_force: dict[str, list[float]] = defaultdict(list)
    grouped_speed: dict[str, list[float]] = defaultdict(list)
    velocity_norms: list[float] = []
    body_heights: list[float] = []
    missing_force = 0
    zero_force = 0
    for row in rows:
        bucket = mode_gait_bucket(row)
        speed_norm = velocity_norm(row)
        if math.isfinite(speed_norm):
            velocity_norms.append(speed_norm)
        body_height = _f(row.get("body_height"))
        if math.isfinite(body_height):
            body_heights.append(body_height)
        for foot in range(4):
            force = _f(row.get(f"foot_force_{foot}"))
            foot_speed = _foot_speed_norm(row, foot)
            if not math.isfinite(force):
                missing_force += 1
                continue
            if force == 0.0:
                zero_force += 1
            foot_key = f"foot_{foot}"
            force_by_foot[foot_key].append(force)
            grouped_force[bucket].append(force)
            if math.isfinite(foot_speed):
                speed_by_foot[foot_key].append(foot_speed)
                grouped_speed[bucket].append(foot_speed)
                force_speed_pairs_by_foot[foot_key][0].append(force)
                force_speed_pairs_by_foot[foot_key][1].append(foot_speed)
    force_stats = {foot: _stats(values) for foot, values in force_by_foot.items()}
    speed_stats = {foot: _stats(values) for foot, values in speed_by_foot.items()}
    force_histograms = {foot: _histogram(values) for foot, values in force_by_foot.items()}
    relationship = {
        foot: {
            "force_speed_corr": _corr(pair[0], pair[1]),
            "paired_count": len(pair[0]),
        }
        for foot, pair in force_speed_pairs_by_foot.items()
    }
    valid_force_total = sum(len(values) for values in force_by_foot.values())
    dynamic_ok = all(
        (stats.get("max") is not None and stats.get("min") is not None and float(stats["max"]) > float(stats["min"]))
        for stats in force_stats.values()
    )
    valid_ratio = valid_force_total / (len(rows) * 4) if rows else 0.0
    field_quality_status = "usable"
    if not rows or valid_ratio < 0.50:
        field_quality_status = "missing_or_sparse"
    elif not dynamic_ok:
        field_quality_status = "constant_or_low_dynamic_range"
    elif zero_force / max(1, valid_force_total) > 0.90:
        field_quality_status = "mostly_zero"
    return {
        "stage": "N7B2_go2_contact_threshold_review",
        "row_count": len(rows),
        "foot_force_stats_by_foot": force_stats,
        "foot_force_histogram_bins": force_histograms,
        "foot_speed_norm_stats_by_foot": speed_stats,
        "foot_force_vs_foot_speed_relationship": relationship,
        "mode_gait_conditioned_distributions": {
            key: {
                "foot_force": _stats(values),
                "foot_speed_norm": _stats(grouped_speed.get(key, [])),
            }
            for key, values in sorted(grouped_force.items())
        },
        "walking_segments_distributions": {
            "foot_force": _stats(grouped_force.get("walking_hint", [])),
            "foot_speed_norm": _stats(grouped_speed.get("walking_hint", [])),
        },
        "standing_segments_distributions": {
            "foot_force": _stats(grouped_force.get("standing_hint", [])),
            "foot_speed_norm": _stats(grouped_speed.get("standing_hint", [])),
        },
        "velocity_norm_stats": _stats(velocity_norms),
        "body_height_stats": _stats(body_heights),
        "missing_force_count": missing_force,
        "zero_force_count": zero_force,
        "valid_force_ratio": valid_ratio,
        "field_quality_status": field_quality_status,
        "distribution_source": "go2_field_distribution_only",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_truth_claim": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_contact_distribution_report(rows: list[dict[str, Any]], output_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = analyze_contact_distribution(rows)
    path = out / "GO2_CONTACT_DISTRIBUTION_REPORT.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
