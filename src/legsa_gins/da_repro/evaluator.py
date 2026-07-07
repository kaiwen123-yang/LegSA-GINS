"""Yaw-only evaluator for DA01 runtime outputs."""

from __future__ import annotations

import bisect
from pathlib import Path
from typing import Any

from .common import as_float, percentile, read_csv_rows, rmse, wrap180


def load_trace_yaw(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for row in read_csv_rows(path):
        t = as_float(row.get("time"), as_float(row.get("timestamp"), as_float(row.get("Time"))))
        yaw = as_float(row.get("yaw"), as_float(row.get("yaw_deg")))
        if t is None or yaw is None:
            continue
        rows.append({"time": t, "yaw_deg": yaw})
    rows.sort(key=lambda item: item["time"])
    return rows


def load_epoch_output(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for row in read_csv_rows(path):
        t = as_float(row.get("timestamp"), as_float(row.get("time")))
        yaw = as_float(row.get("body_yaw_deg"), as_float(row.get("yaw_deg")))
        if t is None or yaw is None:
            continue
        rows.append({"time": t, "yaw_deg": yaw})
    rows.sort(key=lambda item: item["time"])
    return rows


def _nearest(rows: list[dict[str, float]], t: float) -> tuple[dict[str, float], float] | None:
    if not rows:
        return None
    times = [row["time"] for row in rows]
    index = bisect.bisect_left(times, t)
    candidates = []
    if index < len(rows):
        candidates.append(rows[index])
    if index > 0:
        candidates.append(rows[index - 1])
    if not candidates:
        return None
    best = min(candidates, key=lambda row: abs(row["time"] - t))
    return best, t - best["time"]


def evaluate_yaw_only(epoch_output: str | Path, trace_reference: str | Path, *, max_dt: float = 0.10) -> dict[str, Any]:
    est_rows = load_epoch_output(epoch_output)
    trace_rows = load_trace_yaw(trace_reference)
    errors: list[float] = []
    dt_values: list[float] = []
    for est in est_rows:
        match = _nearest(trace_rows, est["time"])
        if match is None:
            continue
        ref, dt = match
        if abs(dt) > max_dt:
            continue
        errors.append(wrap180(est["yaw_deg"] - ref["yaw_deg"]))
        dt_values.append(dt)
    abs_errors = [abs(value) for value in errors]
    return {
        "evaluation_mode": "yaw_only_position_not_applicable",
        "estimate_row_count": len(est_rows),
        "trace_row_count": len(trace_rows),
        "aligned_count": len(errors),
        "max_alignment_dt_sec": max(abs(value) for value in dt_values) if dt_values else None,
        "yaw_rmse_deg": rmse(errors),
        "yaw_mae_deg": sum(abs_errors) / len(abs_errors) if abs_errors else None,
        "yaw_p95_abs_deg": percentile(abs_errors, 0.95),
        "position_metrics": "not_applicable",
        "trace_used_online": False,
        "trace_evaluation_only": True,
        "receiver_imu_data_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
    }
