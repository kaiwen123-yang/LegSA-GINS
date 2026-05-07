"""Trajectory metrics for N4F diagnostic evaluation.

中文说明：本 evaluator 只读取 proposed EVAL_NAV 与 trace evaluation-only reference；
不回写 solver，不做 output-only correction，不删除 bad epoch。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


EARTH_RADIUS_M = 6378137.0
ERROR_HEADER = [
    "timestamp",
    "reference_timestamp",
    "dt",
    "north_error_m",
    "east_error_m",
    "up_error_m",
    "horizontal_error_m",
    "roll_error_deg",
    "pitch_error_deg",
    "yaw_error_deg",
]


def _as_float(value: Any, field: str) -> float:
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing numeric field: {field}")
    return float(value)


def _value_from(raw: dict[str, str], input_name: str) -> Any:
    for candidate in input_name.split("|"):
        value = raw.get(candidate)
        if value is not None and str(value).strip() != "":
            return value
    return raw.get(input_name)


def _load_rows(path: str | Path, field_map: dict[str, str]) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row: dict[str, float] = {}
            for output_name, input_name in field_map.items():
                row[output_name] = _as_float(_value_from(raw, input_name), input_name)
            rows.append(row)
    rows.sort(key=lambda item: item["timestamp"])
    return rows


def load_eval_nav(path: str | Path) -> list[dict[str, float]]:
    return _load_rows(
        path,
        {
            "timestamp": "algo_time_sec|timestamp",
            "lat_deg": "lat_deg",
            "lon_deg": "lon_deg",
            "height_m": "height_m",
            "roll_deg": "roll_deg",
            "pitch_deg": "pitch_deg",
            "yaw_deg": "yaw_deg",
        },
    )


def load_trace_reference(path: str | Path) -> list[dict[str, float]]:
    return _load_rows(
        path,
        {
            "timestamp": "algo_time_sec|timestamp",
            "lat_deg": "lat_deg",
            "lon_deg": "lon_deg",
            "height_m": "height_m",
            "roll_deg": "roll_deg",
            "pitch_deg": "pitch_deg",
            "yaw_deg": "yaw_deg",
        },
    )


def align_by_timestamp(
    est_rows: list[dict[str, float]],
    ref_rows: list[dict[str, float]],
    max_dt: float = 0.05,
) -> list[dict[str, dict[str, float] | float]]:
    aligned: list[dict[str, dict[str, float] | float]] = []
    if not est_rows or not ref_rows:
        return aligned

    ref_index = 0
    for est in est_rows:
        timestamp = est["timestamp"]
        while (
            ref_index + 1 < len(ref_rows)
            and abs(ref_rows[ref_index + 1]["timestamp"] - timestamp)
            <= abs(ref_rows[ref_index]["timestamp"] - timestamp)
        ):
            ref_index += 1
        ref = ref_rows[ref_index]
        dt = timestamp - ref["timestamp"]
        if abs(dt) <= max_dt:
            aligned.append({"est": est, "ref": ref, "dt": dt})
    return aligned


def _wrap_deg(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def compute_errors(
    aligned_rows: list[dict[str, dict[str, float] | float]]
) -> list[dict[str, float]]:
    errors: list[dict[str, float]] = []
    for item in aligned_rows:
        est = item["est"]
        ref = item["ref"]
        if not isinstance(est, dict) or not isinstance(ref, dict):
            raise TypeError("Aligned row must contain est/ref dictionaries.")
        ref_lat_rad = math.radians(ref["lat_deg"])
        dlat_rad = math.radians(est["lat_deg"] - ref["lat_deg"])
        dlon_rad = math.radians(est["lon_deg"] - ref["lon_deg"])
        north = dlat_rad * EARTH_RADIUS_M
        east = dlon_rad * EARTH_RADIUS_M * math.cos(ref_lat_rad)
        up = est["height_m"] - ref["height_m"]
        errors.append(
            {
                "timestamp": est["timestamp"],
                "reference_timestamp": ref["timestamp"],
                "dt": float(item["dt"]),
                "north_error_m": north,
                "east_error_m": east,
                "up_error_m": up,
                "horizontal_error_m": math.hypot(north, east),
                "roll_error_deg": _wrap_deg(est["roll_deg"] - ref["roll_deg"]),
                "pitch_error_deg": _wrap_deg(est["pitch_deg"] - ref["pitch_deg"]),
                "yaw_error_deg": _wrap_deg(est["yaw_deg"] - ref["yaw_deg"]),
            }
        )
    return errors


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = int(math.ceil(0.95 * len(sorted_values))) - 1
    return sorted_values[max(0, min(index, len(sorted_values) - 1))]


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def summary_metrics(errors: list[dict[str, float]]) -> dict[str, Any]:
    horizontal = [abs(row["horizontal_error_m"]) for row in errors]
    up = [row["up_error_m"] for row in errors]
    roll = [row["roll_error_deg"] for row in errors]
    pitch = [row["pitch_error_deg"] for row in errors]
    yaw_abs = [abs(row["yaw_error_deg"]) for row in errors]
    yaw_signed = [row["yaw_error_deg"] for row in errors]
    return {
        "count": len(errors),
        "evidence_status": "diagnostic_aligned"
        if len(errors) > 100
        else "insufficient_alignment",
        "horizontal_rmse_m": _rmse(horizontal),
        "horizontal_p95_m": _p95(horizontal),
        "horizontal_max_m": _max(horizontal),
        "up_rmse_m": _rmse(up),
        "roll_rmse_deg": _rmse(roll),
        "pitch_rmse_deg": _rmse(pitch),
        "yaw_rmse_deg": _rmse(yaw_signed),
        "yaw_p95_deg": _p95(yaw_abs),
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def write_error_series(errors: list[dict[str, float]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ERROR_HEADER)
        writer.writeheader()
        for row in errors:
            writer.writerow({field: row[field] for field in ERROR_HEADER})


def write_summary(summary: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
