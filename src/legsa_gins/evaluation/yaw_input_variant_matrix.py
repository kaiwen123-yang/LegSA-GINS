"""Diagnostic yaw input variant matrix.

中文说明：variant matrix 只用于诊断 yaw sign/offset/source-mode；trace yaw 和
auto-best-by-trace 不能作为 formal solver input 或 formal offset selection。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import median
from typing import Any

from legsa_gins.evaluation.final_v23_input_diff import GNSS_15_COLUMNS, parse_15col_gnss


VARIANTS = [
    ("status_A1_sign+1_offset0_yawstd_fixed1p5_noise0", 1.0, 0.0, False, True),
    ("status_A1_sign+1_offset+90_yawstd_fixed1p5_noise0", 1.0, 90.0, False, True),
    ("status_A1_sign+1_offset-90_yawstd_fixed1p5_noise0", 1.0, -90.0, False, True),
    ("status_A1_sign-1_offset0_yawstd_fixed1p5_noise0", -1.0, 0.0, False, True),
    ("status_A1_sign-1_offset+90_yawstd_fixed1p5_noise0", -1.0, 90.0, False, True),
    ("status_A1_sign-1_offset-90_yawstd_fixed1p5_noise0", -1.0, -90.0, False, True),
    ("status_A1_auto_best_install_diagnostic", 1.0, 0.0, False, False),
    ("trace_yaw_diagnostic_only", 1.0, 0.0, True, False),
    ("status_A1_default_uploaded_script_flags_diagnostic", 1.0, 0.0, False, True),
    ("status_A1_nominal_safe_flags", 1.0, 0.0, False, True),
]


def wrap_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def wrap_360(value: float) -> float:
    return value % 360.0


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "std": None, "min": None, "max": None, "median": None}
    mean = sum(values) / len(values)
    var = sum((value - mean) ** 2 for value in values) / len(values)
    return {
        "count": len(values),
        "mean": mean,
        "std": math.sqrt(var),
        "min": min(values),
        "max": max(values),
        "median": median(values),
    }


def _nearest(rows: list[dict[str, float]], time_value: float, tolerance: float) -> dict[str, float] | None:
    if not rows:
        return None
    best = min(rows, key=lambda row: abs(float(row["time"]) - time_value))
    return best if abs(float(best["time"]) - time_value) <= tolerance else None


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


def load_trace_yaw_from_replay(nav_csv: str | Path, error_series_csv: str | Path) -> list[dict[str, float]]:
    nav_rows: list[dict[str, float]] = []
    with Path(nav_csv).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            time_value = row.get("timestamp", row.get("tow"))
            if time_value is None or row.get("yaw_deg") in {None, ""}:
                continue
            nav_rows.append({"time": float(time_value), "yaw": float(row["yaw_deg"])})
    nav_rows.sort(key=lambda row: row["time"])
    trace: list[dict[str, float]] = []
    nav_index = 0
    with Path(error_series_csv).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("timestamp") in {None, ""} or row.get("yaw_error_deg") in {None, ""}:
                continue
            nav, nav_index = _nearest_sorted(nav_rows, float(row["timestamp"]), nav_index, tolerance=0.05)
            if not nav:
                continue
            trace.append(
                {
                    "time": float(row["timestamp"]),
                    "yaw": wrap_360(nav["yaw"] - float(row["yaw_error_deg"])),
                }
            )
    return trace


def _base_yaw_from_input(row: dict[str, float]) -> float:
    # input yaw is already yaw_ned = 90 - yaw_body. Recover body-like basis for sign tests.
    return wrap_360(90.0 - float(row["yaw"]))


def _variant_yaw(row: dict[str, float], *, sign: float, offset: float) -> float:
    yaw_body = sign * _base_yaw_from_input(row) + offset
    return wrap_360(90.0 - yaw_body)


def _write_variant(path: Path, rows: list[dict[str, float]], yaws: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row, yaw in zip(rows, yaws):
            item = dict(row)
            item["yaw"] = yaw
            item["yaw_std"] = 1.5
            handle.write(" ".join(f"{float(item[key]):.12g}" for key in GNSS_15_COLUMNS) + "\n")


def _yaw_rmse_against_trace(
    times: list[float],
    yaws: list[float],
    trace_rows: list[dict[str, float]],
    *,
    tolerance: float = 0.05,
) -> tuple[float | None, int]:
    errors: list[float] = []
    trace_rows = sorted(trace_rows, key=lambda row: row["time"])
    trace_index = 0
    for time_value, yaw in zip(times, yaws):
        trace, trace_index = _nearest_sorted(trace_rows, time_value, trace_index, tolerance)
        if trace:
            errors.append(wrap_deg(yaw - trace["yaw"]))
    return _rmse(errors), len(errors)


def build_yaw_input_variant_matrix(
    input_gnss: str | Path,
    *,
    trace_yaw_rows: list[dict[str, float]] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    rows = parse_15col_gnss(input_gnss)
    trace_yaw_rows = trace_yaw_rows or []
    out = Path(output_dir) if output_dir else None
    times = [row["time"] for row in rows]
    base_yaws = [row["yaw"] for row in rows]
    trace_by_time = {round(row["time"], 6): row["yaw"] for row in trace_yaw_rows}

    reports: list[dict[str, Any]] = []
    best_status: dict[str, Any] | None = None
    best_trace: dict[str, Any] | None = None
    auto_best_offset = 0.0
    if trace_yaw_rows:
        candidate_offsets = [float(value) for value in range(-180, 181, 5)]
        scored: list[tuple[float, float]] = []
        for offset in candidate_offsets:
            yaws = [_variant_yaw(row, sign=1.0, offset=offset) for row in rows]
            rmse, count = _yaw_rmse_against_trace(times, yaws, trace_yaw_rows)
            if rmse is not None and count >= 3:
                scored.append((rmse, offset))
        if scored:
            auto_best_offset = min(scored)[1]

    for name, sign, offset, trace_variant, formal_allowed_base in VARIANTS:
        if name == "status_A1_auto_best_install_diagnostic":
            offset = auto_best_offset
        if trace_variant and trace_yaw_rows:
            yaws = [trace_by_time.get(round(time_value, 6), base_yaws[index]) for index, time_value in enumerate(times)]
        else:
            yaws = [_variant_yaw(row, sign=sign, offset=offset) for row in rows]
        rmse, matched = _yaw_rmse_against_trace(times, yaws, trace_yaw_rows)
        variant_path = None
        if out:
            variant_path = out / "variants" / f"{name}.gnss"
            _write_variant(variant_path, rows, yaws)
        formal_allowed = bool(formal_allowed_base and not trace_variant and "auto_best" not in name)
        report = {
            "variant_name": name,
            "yaw_vs_trace_rmse_deg": rmse,
            "trace_match_count": matched,
            "yaw_stats": _stats(yaws),
            "yaw_std_stats": _stats([1.5 for _ in yaws]),
            "trace_yaw_for_solver": trace_variant,
            "formal_allowed": formal_allowed,
            "formal_selection_allowed": formal_allowed,
            "yaw_sign": sign,
            "yaw_install_offset_deg": offset,
            "output_path": str(variant_path) if variant_path else None,
        }
        reports.append(report)
        if not trace_variant and name != "status_A1_auto_best_install_diagnostic":
            if best_status is None or (
                report["yaw_vs_trace_rmse_deg"] is not None
                and (
                    best_status.get("yaw_vs_trace_rmse_deg") is None
                    or float(report["yaw_vs_trace_rmse_deg"]) < float(best_status["yaw_vs_trace_rmse_deg"])
                )
            ):
                best_status = report
        if trace_variant:
            best_trace = report
    reports.sort(
        key=lambda item: (
            float("inf") if item.get("yaw_vs_trace_rmse_deg") is None else float(item["yaw_vs_trace_rmse_deg"]),
            item["variant_name"],
        )
    )
    return {
        "variant_count": len(reports),
        "variants": reports,
        "best_status_variant": best_status,
        "best_trace_diagnostic_variant": best_trace,
        "trace_rows": len(trace_yaw_rows),
        "formal_selection_allowed": False,
        "evidence_status": "variant_matrix_with_trace" if trace_yaw_rows else "variant_matrix_without_trace",
        "trace_solver_input": False,
        "numerical_performance_claim": False,
    }
