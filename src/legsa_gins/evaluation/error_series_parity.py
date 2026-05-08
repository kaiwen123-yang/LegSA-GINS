"""Official case-review summary and error-series parity helpers.

中文说明：本模块只比较 evaluator 输出定义；字段缺失时保留 evidence_missing，
不伪造 error_series，也不把 trace/reference 变成 solver input。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


TIME_ALIASES = ["time", "timestamp", "aligned_time", "tow", "algo_time_sec"]
FIELD_ALIASES = {
    "north_error_m": ["north_error_m", "error_n", "err_n_m", "dn", "north_err_m"],
    "east_error_m": ["east_error_m", "error_e", "err_e_m", "de", "east_err_m"],
    "up_error_m": ["up_error_m", "error_u", "err_u_m", "du", "up_err_m"],
    "horizontal_error_m": ["horizontal_error_m", "horizontal_err_m", "horizontal_error", "horizontal_err"],
    "roll_error_deg": ["roll_error_deg", "roll_err_deg"],
    "pitch_error_deg": ["pitch_error_deg", "pitch_err_deg"],
    "yaw_error_deg": ["yaw_error_deg", "yaw_err_deg", "yaw_error", "yaw_err"],
}
SUMMARY_FIELDS = [
    "horizontal_rmse_m",
    "up_rmse_m",
    "yaw_rmse_deg",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "horizontal_p95_m",
    "yaw_p95_deg",
    "aligned_count",
    "count",
]


def _as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_value(raw: dict[str, Any], aliases: list[str]) -> tuple[str | None, float | None]:
    lowered = {str(key).strip().lower(): key for key in raw}
    for alias in aliases:
        key = lowered.get(alias.lower())
        if key is None:
            continue
        value = _as_float(raw.get(key))
        if value is not None:
            return str(key), value
    return None, None


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten(f"{prefix}.{key}" if prefix else str(key), item, out)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _flatten(f"{prefix}.{index}" if prefix else str(index), item, out)
    else:
        out[prefix] = value


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def load_official_error_series(path: str | Path) -> list[dict[str, Any]]:
    """Load official error_series.csv with tolerant field aliases."""

    csv_path = Path(path)
    if not csv_path.exists():
        return [{"evidence_status": "evidence_missing", "evidence_missing": ["error_series.csv"]}]

    rows: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return [{"evidence_status": "evidence_missing", "evidence_missing": ["csv_header"]}]
        for raw in reader:
            row: dict[str, Any] = {}
            missing: list[str] = []
            for key, value in raw.items():
                parsed = _as_float(value)
                if parsed is not None and key:
                    row[str(key)] = parsed
            time_key, timestamp = _first_value(raw, TIME_ALIASES)
            if timestamp is None:
                missing.append("time")
            else:
                row["timestamp"] = timestamp
                row["time_field"] = time_key
            for output_name, aliases in FIELD_ALIASES.items():
                source_key, value = _first_value(raw, aliases)
                if value is None:
                    missing.append(output_name)
                    continue
                row[output_name] = value
                row[f"{output_name}_field"] = source_key
            if missing:
                row["evidence_status"] = "partial"
                row["evidence_missing"] = missing
            else:
                row["evidence_status"] = "parsed"
            rows.append(row)
    rows.sort(key=lambda item: float(item.get("timestamp", 0.0)))
    return rows


def load_official_summary(path: str | Path) -> dict[str, Any]:
    """Load summary.json and extract flat metric names from nested summaries."""

    summary_path = Path(path)
    if not summary_path.exists():
        return {"evidence_status": "evidence_missing", "evidence_missing": ["summary.json"]}
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"evidence_status": "evidence_missing", "evidence_missing": ["summary_json_parse"], "error": str(exc)}

    flat: dict[str, Any] = {}
    _flatten("", data, flat)
    summary: dict[str, Any] = {"evidence_status": "parsed", "raw_summary": data}
    missing: list[str] = []
    for field in SUMMARY_FIELDS:
        value = None
        for key, item in flat.items():
            if key.split(".")[-1] == field or field in key:
                parsed = _as_float(item)
                if parsed is not None:
                    value = parsed
                    break
        if value is None and field not in {"aligned_count", "count"}:
            missing.append(field)
        elif value is not None:
            summary[field] = value
    if "count" not in summary and "aligned_count" in summary:
        summary["count"] = summary["aligned_count"]
    if missing:
        summary["evidence_status"] = "partial"
        summary["evidence_missing"] = missing
    return summary


def compare_summary_metrics(
    official_summary: dict[str, Any],
    recomputed_summary: dict[str, Any],
) -> dict[str, Any]:
    """Compare official summary metrics against recomputed metrics."""

    required = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg"]
    metric_diff: dict[str, float | None] = {}
    missing: list[str] = []
    for metric in [
        "horizontal_rmse_m",
        "up_rmse_m",
        "yaw_rmse_deg",
        "roll_rmse_deg",
        "pitch_rmse_deg",
        "horizontal_p95_m",
        "yaw_p95_deg",
    ]:
        official_value = _as_float(official_summary.get(metric))
        recomputed_value = _as_float(recomputed_summary.get(metric))
        if official_value is None or recomputed_value is None:
            metric_diff[metric] = None
            if metric in required:
                missing.append(metric)
            continue
        metric_diff[metric] = recomputed_value - official_value

    if missing:
        close = False
        status = "evidence_missing"
    else:
        close = (
            abs(float(metric_diff["horizontal_rmse_m"])) < 0.05
            and abs(float(metric_diff["up_rmse_m"])) < 0.05
            and abs(float(metric_diff["yaw_rmse_deg"])) < 0.1
        )
        status = "passed" if close else "mismatch"
    return {
        "metric_diff": metric_diff,
        "summary_close": close,
        "summary_parity_status": status,
        "evidence_missing": missing,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }


def _nearest_sorted(
    rows: list[dict[str, Any]],
    timestamp: float,
    start_index: int,
    tolerance: float,
) -> tuple[dict[str, Any] | None, int]:
    if not rows:
        return None, start_index
    index = min(max(start_index, 0), len(rows) - 1)
    while index + 1 < len(rows) and abs(float(rows[index + 1]["timestamp"]) - timestamp) <= abs(
        float(rows[index]["timestamp"]) - timestamp
    ):
        index += 1
    row = rows[index]
    return (row if abs(float(row["timestamp"]) - timestamp) <= tolerance else None), index


def _has_missing(rows: list[dict[str, Any]], field: str) -> bool:
    return not rows or any(row.get("evidence_status") == "evidence_missing" for row in rows) or all(
        field not in row for row in rows
    )


def compare_error_series(
    official_rows: list[dict[str, Any]],
    recomputed_rows: list[dict[str, Any]],
    *,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Align official and recomputed error series by time and compare errors."""

    if _has_missing(official_rows, "timestamp"):
        return {
            "yaw_error_series_parity_status": "evidence_missing",
            "evidence_missing": ["official_error_series_time"],
            "trace_solver_input": False,
            "output_only_correction": False,
            "numerical_performance_claim": False,
        }
    if _has_missing(official_rows, "yaw_error_deg"):
        return {
            "yaw_error_series_parity_status": "evidence_missing",
            "evidence_missing": ["official_yaw_error_deg"],
            "trace_solver_input": False,
            "output_only_correction": False,
            "numerical_performance_claim": False,
        }

    official_sorted = sorted(official_rows, key=lambda row: float(row["timestamp"]))
    recomputed_sorted = sorted(recomputed_rows, key=lambda row: float(row["timestamp"]))
    index = 0
    paired: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for official in official_sorted:
        match, index = _nearest_sorted(recomputed_sorted, float(official["timestamp"]), index, tolerance)
        if match is not None:
            paired.append((official, match))

    diffs: dict[str, list[float]] = {
        "horizontal_error_m": [],
        "up_error_m": [],
        "roll_error_deg": [],
        "pitch_error_deg": [],
        "yaw_error_deg": [],
    }
    for official, recomputed in paired:
        if "horizontal_error_m" in official and "horizontal_error_m" in recomputed:
            diffs["horizontal_error_m"].append(float(recomputed["horizontal_error_m"]) - float(official["horizontal_error_m"]))
        elif all(key in official for key in ["north_error_m", "east_error_m"]) and all(
            key in recomputed for key in ["north_error_m", "east_error_m"]
        ):
            official_h = math.hypot(float(official["north_error_m"]), float(official["east_error_m"]))
            recomputed_h = math.hypot(float(recomputed["north_error_m"]), float(recomputed["east_error_m"]))
            diffs["horizontal_error_m"].append(recomputed_h - official_h)
        for field in ["up_error_m", "roll_error_deg", "pitch_error_deg", "yaw_error_deg"]:
            if field in official and field in recomputed:
                diffs[field].append(float(recomputed[field]) - float(official[field]))

    yaw_pairwise = diffs["yaw_error_deg"]
    yaw_rmse_diff = _rmse(yaw_pairwise)
    yaw_mean_diff = _mean(yaw_pairwise)
    status = "passed" if paired and yaw_rmse_diff is not None and yaw_rmse_diff < 0.1 else "mismatch"
    return {
        "aligned_count": len(paired),
        "horizontal_error_difference_rmse_m": _rmse(diffs["horizontal_error_m"]),
        "up_error_difference_rmse_m": _rmse(diffs["up_error_m"]),
        "roll_error_difference_rmse_deg": _rmse(diffs["roll_error_deg"]),
        "pitch_error_difference_rmse_deg": _rmse(diffs["pitch_error_deg"]),
        "yaw_error_series_rmse_diff": yaw_rmse_diff,
        "yaw_error_series_mean_diff": yaw_mean_diff,
        "official_yaw_error_rmse_deg": _rmse([float(row["yaw_error_deg"]) for row, _ in paired]),
        "recomputed_yaw_error_rmse_deg": _rmse([float(row["yaw_error_deg"]) for _, row in paired]),
        "yaw_error_series_parity_status": status,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }
