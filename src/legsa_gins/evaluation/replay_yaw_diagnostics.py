"""Replay yaw diagnostics for input, replay NAV, and trace-derived yaw.

中文说明：本模块只做诊断分类；trace yaw 不进入 solver，不做 output-only correction，
也不做 formal performance claim。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.final_v23_input_diff import parse_15col_gnss
from legsa_gins.evaluation.yaw_input_variant_matrix import load_trace_yaw_from_replay, wrap_deg


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _nearest(rows: list[dict[str, float]], time_value: float, tolerance: float) -> dict[str, float] | None:
    if not rows:
        return None
    best = min(rows, key=lambda row: abs(row["time"] - time_value))
    return best if abs(best["time"] - time_value) <= tolerance else None


def _nearest_sorted(
    rows: list[dict[str, float]],
    time_value: float,
    start_index: int,
    tolerance: float,
) -> tuple[dict[str, float] | None, int]:
    if not rows:
        return None, start_index
    index = min(max(start_index, 0), len(rows) - 1)
    while index + 1 < len(rows) and abs(rows[index + 1]["time"] - time_value) <= abs(rows[index]["time"] - time_value):
        index += 1
    best = rows[index]
    return (best if abs(best["time"] - time_value) <= tolerance else None), index


def _load_nav_yaw(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            time_value = row.get("timestamp", row.get("tow"))
            if time_value in {None, ""} or row.get("yaw_deg") in {None, ""}:
                continue
            rows.append({"time": float(time_value), "yaw": float(row["yaw_deg"])})
    return rows


def _pair_rmse(
    rows_a: list[dict[str, float]],
    rows_b: list[dict[str, float]],
    *,
    tolerance: float = 0.05,
) -> tuple[float | None, int]:
    errors: list[float] = []
    rows_a = sorted(rows_a, key=lambda row: row["time"])
    rows_b = sorted(rows_b, key=lambda row: row["time"])
    index = 0
    for row in rows_a:
        other, index = _nearest_sorted(rows_b, row["time"], index, tolerance)
        if other:
            errors.append(wrap_deg(row["yaw"] - other["yaw"]))
    return _rmse(errors), len(errors)


def _constant_offset_issue(value: float | None) -> bool:
    if value is None:
        return False
    for target in [90.0, 180.0]:
        if abs(abs(value) - target) <= 15.0:
            return True
    return False


def compare_input_yaw_to_replay_nav(
    input_gnss: str | Path,
    replay_nav: str | Path,
    output_json: str | Path | None = None,
    *,
    error_series_csv: str | Path | None = None,
) -> dict[str, Any]:
    input_rows = [{"time": row["time"], "yaw": row["yaw"]} for row in parse_15col_gnss(input_gnss)]
    nav_rows = _load_nav_yaw(replay_nav)
    trace_rows = load_trace_yaw_from_replay(replay_nav, error_series_csv) if error_series_csv else []
    input_trace_rmse, input_trace_count = _pair_rmse(input_rows, trace_rows)
    nav_trace_rmse, nav_trace_count = _pair_rmse(nav_rows, trace_rows)
    input_nav_rmse, input_nav_count = _pair_rmse(input_rows, nav_rows)
    if input_trace_rmse is not None and input_trace_rmse <= 5.0 and nav_trace_rmse is not None and nav_trace_rmse > 20.0:
        classification = "likely_runtime_yaw_update_or_initialization_issue"
    elif input_trace_rmse is not None and nav_trace_rmse is not None and input_trace_rmse > 20.0 and nav_trace_rmse > 20.0:
        classification = "likely_input_yaw_generation_issue"
    elif _constant_offset_issue(input_trace_rmse) or _constant_offset_issue(input_nav_rmse):
        classification = "likely_yaw_convention_offset_issue"
    else:
        classification = "evidence_missing" if not trace_rows else "yaw_diagnostics_inconclusive"
    report = {
        "input_yaw_vs_trace_rmse": input_trace_rmse,
        "input_yaw_vs_trace_count": input_trace_count,
        "replay_nav_yaw_vs_trace_rmse": nav_trace_rmse,
        "replay_nav_yaw_vs_trace_count": nav_trace_count,
        "input_yaw_vs_replay_nav_rmse": input_nav_rmse,
        "input_yaw_vs_replay_nav_count": input_nav_count,
        "likely_issue_classification": classification,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }
    if output_json:
        Path(output_json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
