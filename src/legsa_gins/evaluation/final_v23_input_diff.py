"""Compare actual final_v23 `.gnss` input with reconstructed process_data input.

中文说明：本模块只比较 runtime input 文件；不会读取 trace 作为 solver input，
不会做 output-only correction，也不会把差异分析写成 proposed solver performance。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any


GNSS_15_COLUMNS = [
    "time",
    "lat",
    "lon",
    "height",
    "std_n",
    "std_e",
    "std_d",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "yaw",
    "yaw_std",
]


def parse_15col_gnss(path: str | Path) -> list[dict[str, float]]:
    """Parse a whitespace- or comma-separated 15-column `.gnss` file."""

    rows: list[dict[str, float]] = []
    previous_time: float | None = None
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = [part for part in text.replace(",", " ").split() if part]
        if parts and parts[0].lower() == "time":
            continue
        if len(parts) != len(GNSS_15_COLUMNS):
            raise ValueError(f"{path} line {line_number} has {len(parts)} columns; expected 15")
        values = [float(part) for part in parts]
        row = dict(zip(GNSS_15_COLUMNS, values))
        current_time = row["time"]
        if previous_time is not None and current_time < previous_time:
            raise ValueError(f"{path} line {line_number} time is not monotonic")
        previous_time = current_time
        rows.append(row)
    return rows


def nearest_align_by_time(
    rows_a: list[dict[str, float]],
    rows_b: list[dict[str, float]],
    tolerance: float = 0.05,
) -> list[tuple[dict[str, float], dict[str, float], float]]:
    """Nearest-neighbor align rows by `time`; returned dt is `a.time - b.time`."""

    if not rows_a or not rows_b:
        return []
    b_index = 0
    pairs: list[tuple[dict[str, float], dict[str, float], float]] = []
    for row_a in rows_a:
        target = float(row_a["time"])
        while (
            b_index + 1 < len(rows_b)
            and abs(float(rows_b[b_index + 1]["time"]) - target)
            <= abs(float(rows_b[b_index]["time"]) - target)
        ):
            b_index += 1
        row_b = rows_b[b_index]
        dt = target - float(row_b["time"])
        if abs(dt) <= tolerance:
            pairs.append((row_a, row_b, dt))
    return pairs


def _wrap_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None, "rmse": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": _mean(values),
        "median": median(values),
        "rmse": _rmse(values),
    }


def _meters_per_deg_lon(lat_deg: float) -> float:
    return 111_320.0 * math.cos(math.radians(lat_deg))


def compute_gnss_input_diff(
    actual_rows: list[dict[str, float]],
    reconstructed_rows: list[dict[str, float]],
) -> dict[str, Any]:
    """Compare actual and reconstructed 15-column runtime GNSS inputs."""

    pairs = nearest_align_by_time(actual_rows, reconstructed_rows, tolerance=0.05)
    time_diffs: list[float] = []
    horizontal_diffs: list[float] = []
    height_diffs: list[float] = []
    velocity_diffs: list[float] = []
    yaw_diffs: list[float] = []
    yaw_std_diffs: list[float] = []
    std_ned_diffs: list[float] = []
    std_vel_diffs: list[float] = []
    for actual, reconstructed, dt in pairs:
        time_diffs.append(dt)
        mean_lat = (actual["lat"] + reconstructed["lat"]) * 0.5
        dn = (actual["lat"] - reconstructed["lat"]) * 111_320.0
        de = (actual["lon"] - reconstructed["lon"]) * _meters_per_deg_lon(mean_lat)
        horizontal_diffs.append(math.hypot(dn, de))
        height_diffs.append(actual["height"] - reconstructed["height"])
        dvn = actual["vn"] - reconstructed["vn"]
        dve = actual["ve"] - reconstructed["ve"]
        dvd = actual["vd"] - reconstructed["vd"]
        velocity_diffs.append(math.sqrt(dvn * dvn + dve * dve + dvd * dvd))
        yaw_diffs.append(_wrap_deg(actual["yaw"] - reconstructed["yaw"]))
        yaw_std_diffs.append(actual["yaw_std"] - reconstructed["yaw_std"])
        for key in ["std_n", "std_e", "std_d"]:
            std_ned_diffs.append(actual[key] - reconstructed[key])
        for key in ["std_vn", "std_ve", "std_vd"]:
            std_vel_diffs.append(actual[key] - reconstructed[key])

    position_rmse = _rmse(horizontal_diffs)
    yaw_rmse = _rmse(yaw_diffs)
    if len(pairs) < 10:
        status = "evidence_missing"
    elif position_rmse is not None and yaw_rmse is not None and position_rmse <= 0.1 and yaw_rmse > 10.0:
        status = "input_position_matched_but_yaw_mismatch"
    elif yaw_rmse is not None and yaw_rmse <= 2.0:
        status = "yaw_input_matched"
    else:
        status = "input_diff_available"

    return {
        "count": min(len(actual_rows), len(reconstructed_rows)),
        "actual_count": len(actual_rows),
        "reconstructed_count": len(reconstructed_rows),
        "matched_count": len(pairs),
        "time_diff_stats_s": _stats(time_diffs),
        "position_diff_rmse_m": position_rmse,
        "height_diff_rmse_m": _rmse(height_diffs),
        "velocity_diff_rmse_mps": _rmse(velocity_diffs),
        "yaw_diff_rmse_deg": yaw_rmse,
        "yaw_diff_mean_deg": _mean(yaw_diffs),
        "yaw_diff_median_deg": median(yaw_diffs) if yaw_diffs else None,
        "yaw_std_diff_mean_deg": _mean(yaw_std_diffs),
        "std_ned_diff_mean_m": _mean(std_ned_diffs),
        "std_vned_diff_mean_mps": _mean(std_vel_diffs),
        "actual_yaw_stats": _stats([row["yaw"] for row in actual_rows]),
        "reconstructed_yaw_stats": _stats([row["yaw"] for row in reconstructed_rows]),
        "input_diff_status": status,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }


def _flatten(prefix: str, value: Any, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten(f"{prefix}.{key}" if prefix else str(key), item, output)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        output[prefix] = float(value)


def _load_flat_json(path: str | Path) -> dict[str, float]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    flat: dict[str, Any] = {}
    _flatten("", data, flat)
    return {key: float(value) for key, value in flat.items()}


def _find_metric(flat: dict[str, float], field: str) -> float | None:
    lowered = field.lower()
    for key, value in flat.items():
        key_lower = key.lower()
        if key_lower.endswith(lowered) or lowered in key_lower:
            return value
    return None


def compare_actual_final_v23_summary(
    actual_summary_path: str | Path,
    n4h2_summary_path: str | Path,
) -> dict[str, Any]:
    """Compare actual final_v23 summary JSON against the N4H2 diagnostic summary."""

    actual = Path(actual_summary_path)
    n4h2 = Path(n4h2_summary_path)
    if not actual.exists() or not n4h2.exists():
        return {
            "evidence_status": "evidence_missing",
            "actual_summary_exists": actual.exists(),
            "n4h2_summary_exists": n4h2.exists(),
        }
    actual_flat = _load_flat_json(actual)
    n4h2_flat = _load_flat_json(n4h2)
    fields = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]
    comparisons: dict[str, dict[str, float | None]] = {}
    for field in fields:
        actual_value = _find_metric(actual_flat, field)
        n4h2_value = _find_metric(n4h2_flat, field)
        comparisons[field] = {
            "actual": actual_value,
            "n4h2": n4h2_value,
            "diff": None if actual_value is None or n4h2_value is None else n4h2_value - actual_value,
        }
    return {
        "evidence_status": "summary_compared",
        "actual_summary_exists": True,
        "n4h2_summary_exists": True,
        "metric_diff": comparisons,
        "trace_solver_input": False,
        "numerical_performance_claim": False,
    }
