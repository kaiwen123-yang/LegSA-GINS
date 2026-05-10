"""Diagnostics for N5C raw Doppler factor files.

中文说明：这些统计只用于 factor 质量和一致性检查，不是论文性能结果。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def _float(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _finite(values: list[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def _p(values: list[float], percentile: float) -> float | None:
    values = sorted(_finite(values))
    if not values:
        return None
    idx = max(0, min(len(values) - 1, math.ceil(percentile * len(values)) - 1))
    return values[idx]


def _stats(values: list[float]) -> dict[str, float | None]:
    finite = _finite(values)
    return {
        "min": min(finite) if finite else None,
        "p50": _p(finite, 0.50),
        "p95": _p(finite, 0.95),
        "max": max(finite) if finite else None,
    }


def analyze_raw_doppler_factor_csv(
    factor_csv: str | Path,
    *,
    clean_start: float | None = None,
    clean_end: float | None = None,
) -> dict[str, Any]:
    rows = _rows(factor_csv)
    times = _finite([_float(row.get("time")) for row in rows])
    sat = [int(_float(row.get("sat_count"), 0.0)) for row in rows]
    velocities = {axis: [_float(row.get(axis)) for row in rows] for axis in ["vn", "ve", "vd"]}
    stds = {axis: [_float(row.get(axis)) for row in rows] for axis in ["std_vn", "std_ve", "std_vd"]}
    gaps = [b - a for a, b in zip(times, times[1:])]
    overlap_count = 0
    if clean_start is not None and clean_end is not None:
        overlap_count = sum(clean_start <= time <= clean_end for time in times)
    spike_count = 0
    for prev, cur in zip(rows, rows[1:]):
        dv = math.sqrt(sum((_float(cur.get(axis), 0.0) - _float(prev.get(axis), 0.0)) ** 2 for axis in ["vn", "ve", "vd"]))
        if dv > 5.0:
            spike_count += 1
    std_spikes = sum(max(_float(row.get("std_vn"), 0.0), _float(row.get("std_ve"), 0.0), _float(row.get("std_vd"), 0.0)) > 5.0 for row in rows)
    quality: dict[str, int] = {}
    for row in rows:
        flag = row.get("quality_flag", "")
        quality[flag] = quality.get(flag, 0) + 1
    return {
        "epoch_count": len(rows),
        "valid_epoch_count": sum(row.get("provider_status") == "available" for row in rows),
        "time_range": [min(times), max(times)] if times else None,
        "sat_count_min": min(sat) if sat else 0,
        "sat_count_median": sorted(sat)[len(sat) // 2] if sat else 0,
        "sat_count_max": max(sat) if sat else 0,
        "std_stats": {axis: _stats(values) for axis, values in stds.items()},
        "std_vn_p95": _stats(stds["std_vn"])["p95"],
        "std_ve_p95": _stats(stds["std_ve"])["p95"],
        "std_vd_p95": _stats(stds["std_vd"])["p95"],
        "velocity_range": {axis: {"min": _stats(values)["min"], "max": _stats(values)["max"]} for axis, values in velocities.items()},
        "gap_statistics": _stats(gaps),
        "overlap_epoch_count": overlap_count,
        "quality_flag_counts": quality,
        "covariance_available": all(_float(row.get("std_vn"), 0.0) > 0 and _float(row.get("std_ve"), 0.0) > 0 and _float(row.get("std_vd"), 0.0) > 0 for row in rows),
        "suspicious_velocity_spikes": spike_count,
        "suspicious_std_spikes": std_spikes,
        "paper_performance_claim": False,
    }


def analyze_raw_doppler_update_trace(run_manifest: dict[str, Any]) -> dict[str, Any]:
    update_count = int(run_manifest.get("raw_doppler_update_count", 0) or 0)
    reject_count = int(run_manifest.get("raw_doppler_reject_count", 0) or 0)
    total = update_count + reject_count
    return {
        "raw_doppler_update_count": update_count,
        "raw_doppler_reject_count": reject_count,
        "raw_doppler_residual_p95": run_manifest.get("raw_doppler_residual_p95"),
        "rejection_ratio": reject_count / total if total else 0.0,
        "matched_epoch_count": update_count,
        "unmatched_epoch_count": max(0, int(run_manifest.get("raw_doppler_factor_valid_epoch_count", 0) or 0) - update_count),
        "paper_performance_claim": False,
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
