"""Time alignment checks for N7A Go2 weak prior.

中文说明：aligned_time = stamp - BASE_TIME；不从 trace 或 final_v23 输出估计物理
clock offset，只检查 Go2 与 clean replay 时间窗的重叠。
"""

from __future__ import annotations

import csv
import json
import math
from bisect import bisect_left
from pathlib import Path
from typing import Any

from .go2_weak_prior_types import TimeWindow


def _as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _read_times(path: str | Path) -> list[float]:
    source = Path(path)
    if not source.exists():
        return []
    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            key = "time" if "time" in fields else fields[0] if fields else ""
            return [value for value in (_as_float(row.get(key)) for row in reader) if value is not None]
    out: list[float] = []
    with source.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            value = _as_float(line.split()[0])
            if value is not None:
                out.append(value)
    return out


def find_clean_replay_times(clean_root: str | Path) -> list[float]:
    root = Path(clean_root).resolve()
    for candidate in [
        root / "EVAL_NAV.csv",
        root / "LegSA_PORT_NAV.nav",
        root / "CLEAN_STATUS_YAW.imu",
        root / "CLEAN_STATUS_YAW.gnss",
        root / "inputs" / "input.imu",
        root / "input.imu",
    ]:
        times = _read_times(candidate)
        if times:
            return times
    return []


def clean_window_from_times(times: list[float]) -> TimeWindow:
    if not times:
        return TimeWindow(0.0, 0.0)
    return TimeWindow(min(times), max(times))


def _nearest_p95(query_times: list[float], reference_times: list[float]) -> float | None:
    if not query_times or not reference_times:
        return None
    ref = sorted(reference_times)
    deltas: list[float] = []
    for value in query_times:
        pos = bisect_left(ref, value)
        choices = []
        if pos < len(ref):
            choices.append(abs(ref[pos] - value))
        if pos > 0:
            choices.append(abs(ref[pos - 1] - value))
        if choices:
            deltas.append(min(choices))
    if not deltas:
        return None
    ordered = sorted(deltas)
    return ordered[int(0.95 * (len(ordered) - 1))]


def build_time_alignment_report(
    rows: list[dict[str, Any]],
    clean_times: list[float],
    *,
    tolerance_sec: float = 0.02,
) -> dict[str, Any]:
    go2_times = [value for value in (_as_float(row.get("aligned_time")) for row in rows) if value is not None]
    go2_window = clean_window_from_times(go2_times)
    clean_window = clean_window_from_times(clean_times)
    overlap = TimeWindow(max(go2_window.start, clean_window.start), min(go2_window.end, clean_window.end))
    overlap_times = [value for value in go2_times if overlap.contains(value)]
    nearest_p95 = _nearest_p95(overlap_times[:: max(1, len(overlap_times) // 5000)], clean_times)
    alignment_ok = overlap.duration > 0.0 and (nearest_p95 is None or nearest_p95 <= tolerance_sec)
    return {
        "go2_start": go2_window.start if go2_times else None,
        "go2_end": go2_window.end if go2_times else None,
        "clean_start": clean_window.start if clean_times else None,
        "clean_end": clean_window.end if clean_times else None,
        "overlap_start": overlap.start if overlap.duration > 0.0 else None,
        "overlap_end": overlap.end if overlap.duration > 0.0 else None,
        "overlap_duration": overlap.duration,
        "expected_prior_count": len(overlap_times),
        "time_alignment_ok": alignment_ok,
        "nearest_match_p95": nearest_p95,
        "activation_allowed": alignment_ok and len(overlap_times) > 0,
        "time_tolerance_sec": tolerance_sec,
        "alignment_uses_trace": False,
        "alignment_uses_final_v23_output": False,
    }


def write_time_alignment_report(
    rows: list[dict[str, Any]],
    clean_times: list[float],
    output_path: str | Path,
    *,
    tolerance_sec: float = 0.02,
) -> dict[str, Any]:
    report = build_time_alignment_report(rows, clean_times, tolerance_sec=tolerance_sec)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
