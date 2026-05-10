"""N5C raw Doppler factor time alignment diagnostics.

中文说明：只检查 factor 与 clean GNSS/IMU 时间重叠，不用 trace 调整时间。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def read_first_column_times(path: str | Path) -> list[float]:
    times: list[float] = []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        time = _f(line.split()[0])
        if math.isfinite(time):
            times.append(time)
    return times


def _factor_times(path: str | Path) -> list[float]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [_f(row.get("time")) for row in csv.DictReader(handle)]


def _p(values: list[float], percentile: float) -> float | None:
    finite = sorted(abs(value) for value in values if math.isfinite(value))
    if not finite:
        return None
    return finite[max(0, min(len(finite) - 1, math.ceil(percentile * len(finite)) - 1))]


def analyze_factor_time_alignment(
    factor_csv: str | Path,
    gnss_times: list[float],
    imu_times: list[float],
    run_manifest: dict[str, Any] | None = None,
    *,
    tolerance: float = 0.08,
) -> dict[str, Any]:
    factor = sorted(t for t in _factor_times(factor_csv) if math.isfinite(t))
    if not factor or not gnss_times or not imu_times:
        return {
            "factor_epoch_count": len(factor),
            "overlap_epoch_count": 0,
            "expected_update_count": 0,
            "actual_update_count": int((run_manifest or {}).get("raw_doppler_update_count", 0) or 0),
            "update_alignment_ok": False,
            "recommended_tolerance_if_not_ok": tolerance,
            "trace_solver_input": False,
            "paper_performance_claim": False,
        }
    overlap_start = max(min(gnss_times), min(imu_times))
    overlap_end = min(max(gnss_times), max(imu_times))
    gnss_overlap = [time for time in gnss_times if overlap_start <= time <= overlap_end]
    diffs: list[float] = []
    matched = 0
    idx = 0
    for time in gnss_overlap:
        while idx + 1 < len(factor) and abs(factor[idx + 1] - time) <= abs(factor[idx] - time):
            idx += 1
        diff = factor[idx] - time
        diffs.append(diff)
        if abs(diff) <= tolerance:
            matched += 1
    actual = int((run_manifest or {}).get("raw_doppler_update_count", 0) or 0)
    ok = matched == len(gnss_overlap) and (actual == 0 or actual == matched)
    return {
        "factor_epoch_count": len(factor),
        "overlap_epoch_count": len(gnss_overlap),
        "expected_update_count": matched,
        "actual_update_count": actual,
        "time_diff_p50": _p(diffs, 0.50),
        "time_diff_p95": _p(diffs, 0.95),
        "time_diff_max": max((abs(value) for value in diffs), default=None),
        "unmatched_factor_epochs": max(0, len(factor) - matched),
        "unmatched_update_epochs": max(0, len(gnss_overlap) - actual),
        "update_alignment_ok": ok,
        "recommended_tolerance_if_not_ok": None if ok else max(tolerance, (_p(diffs, 0.95) or tolerance) * 1.2),
        "trace_solver_input": False,
        "paper_performance_claim": False,
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
