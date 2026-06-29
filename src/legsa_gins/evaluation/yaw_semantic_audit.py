"""PAPER10M1R2C1 yaw semantic audit helpers.

This module is evaluator-side only. It reads existing NAV/EVAL_NAV/reference
artifacts and computes diagnostic yaw convention candidates. It does not run a
solver, regenerate providers, tune by trace, delete epochs, or modify outputs.
"""

from __future__ import annotations

import bisect
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


METHODS = [
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
]

YAW_TRANSFORM_CANDIDATES = [
    "direct_yaw",
    "wrap_only",
    "plus_90_deg",
    "minus_90_deg",
    "plus_180_deg",
    "sign_flip",
    "ENU_NED_swap",
    "body_heading_from_lateral_baseline_plus_90",
    "body_heading_from_lateral_baseline_minus_90",
    "rad_deg_misread",
]


@dataclass(frozen=True)
class YawReference:
    name: str
    rows: list[dict[str, float]]
    interpolation: str = "nearest"
    role: str = "evaluation_only"


def safe_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        text = str(value).replace("[[", "").replace("]]", "")
        return float(text)
    except (TypeError, ValueError):
        return default


def wrap_deg180(angle: float) -> float:
    wrapped = (float(angle) + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def wrap_deg360(angle: float) -> float:
    return float(angle) % 360.0


def rmse(values: Iterable[float]) -> float:
    values = [float(value) for value in values if math.isfinite(float(value))]
    if not values:
        return math.nan
    return math.sqrt(sum(value * value for value in values) / len(values))


def p95_abs(values: Iterable[float]) -> float:
    values = sorted(abs(float(value)) for value in values if math.isfinite(float(value)))
    if not values:
        return math.nan
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * 0.95))))
    return values[index]


def transform_yaw_deg(value: float, transform_name: str) -> float:
    value = float(value)
    if transform_name in {"direct_yaw", "wrap_only", "identity"}:
        transformed = value
    elif transform_name in {"plus_90_deg", "body_heading_from_lateral_baseline_plus_90"}:
        transformed = value + 90.0
    elif transform_name in {"minus_90_deg", "body_heading_from_lateral_baseline_minus_90"}:
        transformed = value - 90.0
    elif transform_name == "plus_180_deg":
        transformed = value + 180.0
    elif transform_name == "sign_flip":
        transformed = -value
    elif transform_name == "ENU_NED_swap":
        transformed = 90.0 - value
    elif transform_name == "rad_deg_misread":
        transformed = math.degrees(value)
    else:
        raise ValueError(f"unknown yaw transform: {transform_name}")
    return wrap_deg360(transformed)


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in fieldnames})


def _csv_value(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.12g}"
    return "" if value is None else str(value)


def read_eval_nav_yaw(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for row in read_csv_rows(path):
        time_value = safe_float(row.get("time", row.get("timestamp")))
        yaw_value = safe_float(row.get("yaw_deg", row.get("yaw")))
        if math.isfinite(time_value) and math.isfinite(yaw_value):
            rows.append({"time": time_value, "yaw_deg": wrap_deg360(yaw_value)})
    return rows


def read_15col_yaw(path: str | Path, *, name: str, role: str) -> YawReference:
    rows: list[dict[str, float]] = []
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 14:
                continue
            time_value = safe_float(parts[0])
            yaw_value = safe_float(parts[13])
            if math.isfinite(time_value) and math.isfinite(yaw_value):
                rows.append({"time": time_value, "yaw_deg": wrap_deg360(yaw_value)})
    return YawReference(name=name, rows=rows, interpolation="nearest", role=role)


def read_raw_trace_heading_to_math(
    path: str | Path,
    *,
    name: str = "trace_heading_to_math",
    epoch_floor: float | None = None,
) -> YawReference:
    raw = read_csv_rows(path)
    if not raw:
        return YawReference(name=name, rows=[], interpolation="linear_unwrapped", role="trace_evaluation_only")
    first_time = safe_float(raw[0].get("time"))
    if epoch_floor is None and first_time > 1.0e9:
        epoch_floor = math.floor(first_time / 100.0) * 100.0
    elif epoch_floor is None:
        epoch_floor = 0.0
    rows: list[dict[str, float]] = []
    for row in raw:
        time_value = safe_float(row.get("time")) - epoch_floor
        yaw_heading = safe_float(row.get("yaw"))
        if math.isfinite(time_value) and math.isfinite(yaw_heading):
            rows.append({"time": time_value, "yaw_deg": wrap_deg360(90.0 - yaw_heading)})
    return YawReference(name=name, rows=rows, interpolation="linear_unwrapped", role="trace_evaluation_only")


def _unwrapped_yaws(rows: list[dict[str, float]]) -> list[float]:
    if not rows:
        return []
    values = [row["yaw_deg"] for row in rows]
    out = [values[0]]
    previous_wrapped = values[0]
    for value in values[1:]:
        out.append(out[-1] + wrap_deg180(value - previous_wrapped))
        previous_wrapped = value
    return out


def _reference_yaw_at_cached(
    reference: YawReference,
    time_value: float,
    *,
    max_dt: float,
    times: list[float],
    unwrapped: list[float],
) -> float | None:
    if not reference.rows or not times:
        return None
    index = bisect.bisect_left(times, time_value)
    if reference.interpolation == "linear_unwrapped" and 0 < index < len(times):
        left = index - 1
        right = index
        if time_value < times[left] or time_value > times[right]:
            return None
        if min(abs(time_value - times[left]), abs(time_value - times[right])) > max_dt:
            return None
        span = times[right] - times[left]
        if span <= 0.0:
            return wrap_deg360(unwrapped[left])
        fraction = (time_value - times[left]) / span
        return wrap_deg360(unwrapped[left] + fraction * (unwrapped[right] - unwrapped[left]))
    candidates: list[int] = []
    if index < len(times):
        candidates.append(index)
    if index > 0:
        candidates.append(index - 1)
    if not candidates:
        return None
    best = min(candidates, key=lambda item: abs(times[item] - time_value))
    if abs(times[best] - time_value) > max_dt:
        return None
    return reference.rows[best]["yaw_deg"]


def yaw_errors_for_reference(
    nav_rows: list[dict[str, float]],
    reference: YawReference,
    *,
    transform_name: str = "direct_yaw",
    max_dt: float = 0.25,
    nav_stride: int = 1,
) -> list[float]:
    errors: list[float] = []
    if not nav_rows or not reference.rows:
        return errors
    times = [row["time"] for row in reference.rows]
    unwrapped = _unwrapped_yaws(reference.rows) if reference.interpolation == "linear_unwrapped" else []
    for row in nav_rows[:: max(1, nav_stride)]:
        ref_yaw = _reference_yaw_at_cached(reference, row["time"], max_dt=max_dt, times=times, unwrapped=unwrapped)
        if ref_yaw is None:
            continue
        transformed = transform_yaw_deg(ref_yaw, transform_name)
        errors.append(wrap_deg180(row["yaw_deg"] - transformed))
    return errors


def summarize_errors(errors: list[float]) -> dict[str, Any]:
    return {
        "row_count": len(errors),
        "yaw_rmse_deg": rmse(errors),
        "yaw_mean_error_deg": sum(errors) / len(errors) if errors else math.nan,
        "yaw_p95_abs_error_deg": p95_abs(errors),
        "yaw_max_abs_error_deg": max((abs(value) for value in errors), default=math.nan),
    }


def audit_transform_candidates(
    nav_rows: list[dict[str, float]],
    reference: YawReference,
    *,
    max_dt: float = 0.25,
    nav_stride: int = 1,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for transform_name in YAW_TRANSFORM_CANDIDATES:
        errors = yaw_errors_for_reference(
            nav_rows,
            reference,
            transform_name=transform_name,
            max_dt=max_dt,
            nav_stride=nav_stride,
        )
        summary = summarize_errors(errors)
        rows.append(
            {
                "reference_name": reference.name,
                "reference_role": reference.role,
                "yaw_transform_candidate": transform_name,
                **summary,
            }
        )
    return rows


def best_candidate(candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in candidate_rows if _finite(row.get("yaw_rmse_deg"))]
    if not valid:
        return {}
    return min(valid, key=lambda row: float(row["yaw_rmse_deg"]))


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def classify_clean_yaw_gate(clean_method_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify M1R2C1 yaw status without changing solver outputs."""

    strong_like = [
        row
        for row in clean_method_rows
        if row.get("method_mode_id") in {"strong_dual_yaw_baseline", "legsa_without_qm", "legsa_full_candidate_with_qm"}
    ]
    trace_failures = [
        row
        for row in strong_like
        if _finite(row.get("trace_heading_to_math_rmse_deg")) and float(row["trace_heading_to_math_rmse_deg"]) > 10.0
    ]
    provider_failures = [
        row
        for row in strong_like
        if _finite(row.get("best_provider_reference_rmse_deg")) and float(row["best_provider_reference_rmse_deg"]) > 10.0
    ]
    if trace_failures:
        return {
            "clean_yaw_semantics_resolved": False,
            "evaluator_only_repair": False,
            "gate_status": "BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE",
            "reason": "clean strong/LegSA yaw remains above 10 deg against trace heading-to-math reference",
        }
    if provider_failures:
        return {
            "clean_yaw_semantics_resolved": False,
            "evaluator_only_repair": False,
            "gate_status": "BLOCKED_CLEAN_YAW_SEMANTIC_FAILURE",
            "reason": "clean yaw cannot be recovered by evaluator transform candidates against provider yaw",
        }
    return {
        "clean_yaw_semantics_resolved": True,
        "evaluator_only_repair": True,
        "gate_status": "CLEAN_YAW_EVALUATOR_ONLY_CANDIDATE",
        "reason": "clean yaw is within gate after evaluator-only convention selection",
    }
