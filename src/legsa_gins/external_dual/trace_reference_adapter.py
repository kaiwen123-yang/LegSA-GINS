"""Trace adapter used only for evaluation."""

from __future__ import annotations

import csv
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TraceYawEpoch:
    time: float
    yaw_deg: float


def load_trace_yaw(path: Path) -> list[TraceYawEpoch]:
    rows: list[TraceYawEpoch] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            try:
                rows.append(TraceYawEpoch(float(row["time"]), float(row["yaw"]) % 360.0))
            except (KeyError, TypeError, ValueError):
                continue
    rows.sort(key=lambda item: item.time)
    return rows


def nearest_trace_yaw(trace: list[TraceYawEpoch], time_s: float, *, max_dt_s: float = 0.5) -> TraceYawEpoch | None:
    if not trace:
        return None
    times = [item.time for item in trace]
    pos = bisect_left(times, time_s)
    candidates = []
    if pos < len(trace):
        candidates.append(trace[pos])
    if pos:
        candidates.append(trace[pos - 1])
    if not candidates:
        return None
    nearest = min(candidates, key=lambda item: abs(item.time - time_s))
    return nearest if abs(nearest.time - time_s) <= max_dt_s else None


def summarize_trace(trace: list[TraceYawEpoch]) -> dict[str, str]:
    return {"epoch_count": str(len(trace)), "evaluation_reference_only": "true", "solver_input_allowed": "false", "yaw_sign_or_offset_selection_allowed": "false"}
