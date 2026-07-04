"""Offline evaluator for DA3R2 yaw estimates."""

from __future__ import annotations

import csv
import math
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path

from .method_runner import MethodEstimate
from .yaw_frame_contract import yaw_error_deg


@dataclass(frozen=True)
class TraceYaw:
    time: float
    yaw_deg: float


def read_trace_yaw(path: str | Path) -> list[TraceYaw]:
    rows: list[TraceYaw] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append(TraceYaw(float(row["time"]), float(row["yaw"])))
            except (KeyError, TypeError, ValueError):
                continue
    rows.sort(key=lambda row: row.time)
    return rows


def evaluate_estimates(estimates: list[MethodEstimate], trace: list[TraceYaw]) -> dict[str, object]:
    trace_times = [row.time for row in trace]
    errors: list[float] = []
    for estimate in estimates:
        ref = _nearest(trace, trace_times, estimate.time)
        if ref is None:
            continue
        errors.append(yaw_error_deg(estimate.body_yaw_deg, ref.yaw_deg))
    abs_errors = [abs(value) for value in errors]
    return {
        "epoch_count": len(estimates),
        "valid_provider_epoch_count": sum(1 for row in estimates if row.valid),
        "yaw_metric_count": len(errors),
        "yaw_rmse_deg": _rmse(errors),
        "yaw_mae_deg": sum(abs_errors) / len(abs_errors) if abs_errors else None,
        "yaw_p95_deg": _percentile(abs_errors, 0.95),
        "yaw_max_abs_deg": max(abs_errors) if abs_errors else None,
        "horizontal_rmse_m": None,
        "up_rmse_m": None,
        "position_metric_applicable": False,
        "yaw_metric_applicable": True,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_solver_input": False,
        "legsa_solver_input": False,
        "yaw_frame_safe": True,
        "wrap_safe": True,
    }


def write_eval_metrics(metrics: dict[str, object], path: str | Path) -> None:
    import json

    Path(path).write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _nearest(trace: list[TraceYaw], times: list[float], time_s: float) -> TraceYaw | None:
    if not trace:
        return None
    pos = bisect_left(times, time_s)
    candidates = []
    if pos < len(trace):
        candidates.append(trace[pos])
    if pos:
        candidates.append(trace[pos - 1])
    if not candidates:
        return None
    best = min(candidates, key=lambda row: abs(row.time - time_s))
    return best if abs(best.time - time_s) <= 1.0 else None


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = min(len(values) - 1, max(0, int(math.ceil(q * len(values))) - 1))
    return values[index]
