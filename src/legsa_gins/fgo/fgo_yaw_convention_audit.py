"""N8A1 yaw convention and wrap audit helpers.

中文说明：本模块只审查 yaw 单位、环绕和残差约定，不修改 solver。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json_report(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        return {}
    return json.loads(json_path.read_text(encoding="utf-8"))


def write_json_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return fallback
    return result if math.isfinite(result) else fallback


def yaw_series(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        if "yaw_deg" in row:
            values.append(as_float(row.get("yaw_deg")))
        elif "yaw" in row:
            values.append(as_float(row.get("yaw")))
        elif "heading_deg" in row:
            values.append(as_float(row.get("heading_deg")))
    return values


def time_series(rows: list[dict[str, Any]]) -> list[float]:
    return [as_float(row.get("time", row.get("timestamp", index)), float(index)) for index, row in enumerate(rows)]


def wrap_delta_deg(delta_deg: float) -> float:
    wrapped = (delta_deg + 180.0) % 360.0 - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped


def yaw_delta_deg(candidate_deg: float, reference_deg: float) -> float:
    return wrap_delta_deg(candidate_deg - reference_deg)


def wrap_angle_0_360(angle_deg: float) -> float:
    return angle_deg % 360.0


def unwrap_degrees(values: list[float]) -> list[float]:
    if not values:
        return []
    unwrapped = [values[0]]
    for value in values[1:]:
        previous = unwrapped[-1]
        delta = wrap_delta_deg(value - previous)
        unwrapped.append(previous + delta)
    return unwrapped


def rmse(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else 0.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def classify_yaw_unit(values: list[float], column_name: str = "yaw_deg") -> str:
    if not values:
        return "unknown"
    finite = [abs(value) for value in values if math.isfinite(value)]
    if not finite:
        return "unknown"
    max_abs = max(finite)
    if column_name.endswith("_deg") or max_abs > (2.0 * math.pi + 0.5):
        return "deg"
    return "rad"


def classify_yaw_range(values: list[float]) -> str:
    if not values:
        return "unknown"
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return "unknown"
    min_value = min(finite)
    max_value = max(finite)
    if 0.0 <= min_value and max_value <= 360.0:
        return "0_to_360"
    if -180.0 <= min_value and max_value <= 180.0:
        return "minus180_to_180"
    if max_value - min_value > 360.0:
        return "continuous_unwrapped"
    return "mixed_or_offset"


def count_yaw_jumps(values: list[float], *, threshold_deg: float = 90.0) -> int:
    count = 0
    for left, right in zip(values, values[1:]):
        if abs(wrap_delta_deg(right - left)) > threshold_deg:
            count += 1
    return count


def count_wrap_boundary_pairs(values: list[float]) -> int:
    count = 0
    for left, right in zip(values, values[1:]):
        raw = abs(right - left)
        wrapped = abs(wrap_delta_deg(right - left))
        if raw > 300.0 and wrapped < 60.0:
            count += 1
    return count


def count_wrap_averaging_artifacts(ekf_yaw: list[float], fgo_yaw: list[float]) -> int:
    count = 0
    for ekf_value, fgo_value in zip(ekf_yaw, fgo_yaw):
        near_wrap = ekf_value % 360.0 <= 20.0 or ekf_value % 360.0 >= 340.0
        if near_wrap and abs(yaw_delta_deg(fgo_value, ekf_value)) > 90.0:
            count += 1
    return count


def _heading_math_transform_rmse(ekf_yaw: list[float], fgo_yaw: list[float]) -> dict[str, float]:
    count = min(len(ekf_yaw), len(fgo_yaw))
    pairs = list(zip(ekf_yaw[:count], fgo_yaw[:count]))
    transforms = {
        "identity": lambda value: value,
        "negative_heading": lambda value: -value,
        "math_from_heading_90_minus": lambda value: 90.0 - value,
        "heading_from_math_90_plus": lambda value: 90.0 + value,
    }
    return {
        name: rmse([yaw_delta_deg(transform(fgo), ekf) for ekf, fgo in pairs])
        for name, transform in transforms.items()
    }


def audit_yaw_convention(
    *,
    ekf_rows: list[dict[str, Any]],
    fgo_rows: list[dict[str, Any]],
    evaluation_report: dict[str, Any] | None = None,
    smoother_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit yaw units, wrap behavior, and residual convention without changing solver output."""
    evaluation = evaluation_report or {}
    smoother = smoother_report or {}
    ekf_yaw = yaw_series(ekf_rows)
    fgo_yaw = yaw_series(fgo_rows)
    count = min(len(ekf_yaw), len(fgo_yaw))
    ekf_yaw = ekf_yaw[:count]
    fgo_yaw = fgo_yaw[:count]
    raw_deltas = [fgo - ekf for ekf, fgo in zip(ekf_yaw, fgo_yaw)]
    wrapped_deltas = [yaw_delta_deg(fgo, ekf) for ekf, fgo in zip(ekf_yaw, fgo_yaw)]
    raw_rmse = rmse(raw_deltas)
    wrapped_rmse = rmse(wrapped_deltas)
    transform_rmse = _heading_math_transform_rmse(ekf_yaw, fgo_yaw)
    identity_rmse = transform_rmse.get("identity", wrapped_rmse)
    best_nonidentity = min((value for name, value in transform_rmse.items() if name != "identity"), default=identity_rmse)
    heading_math_mismatch_suspect = bool(identity_rmse > 5.0 and best_nonidentity < identity_rmse * 0.5)
    wrap_boundary_pair_count = count_wrap_boundary_pairs(ekf_yaw)
    wrap_averaging_artifact_count = count_wrap_averaging_artifacts(ekf_yaw, fgo_yaw)
    yaw_jump_count = count_yaw_jumps(fgo_yaw)
    ekf_jump_count = count_yaw_jumps(ekf_yaw)
    yaw_residual_wrap_used = not (wrap_averaging_artifact_count > 0 and wrap_boundary_pair_count > 0)
    yaw_wrap_consistent = yaw_residual_wrap_used and yaw_jump_count <= max(ekf_jump_count + 2, 4)
    yaw_unit_consistent = classify_yaw_unit(ekf_yaw) == "deg" and classify_yaw_unit(fgo_yaw) == "deg"
    if not yaw_unit_consistent:
        blocker_status = "yaw_unit_blocker"
    elif not yaw_wrap_consistent:
        blocker_status = "yaw_wrap_residual_blocker"
    elif heading_math_mismatch_suspect:
        blocker_status = "heading_math_yaw_convention_review"
    else:
        blocker_status = "clear"
    return {
        "stage": "N8A1_fgo_yaw_delta_policy_review",
        "source_role_alias": "N8A_REPORT_OUTPUT_DIR",
        "aligned_state_count": count,
        "yaw_unit_consistent": yaw_unit_consistent,
        "ekf_yaw_unit_inferred": classify_yaw_unit(ekf_yaw),
        "fgo_yaw_unit_inferred": classify_yaw_unit(fgo_yaw),
        "ekf_yaw_range_inferred": classify_yaw_range(ekf_yaw),
        "fgo_yaw_range_inferred": classify_yaw_range(fgo_yaw),
        "yaw_wrap_consistent": yaw_wrap_consistent,
        "heading_math_yaw_mismatch_suspect": heading_math_mismatch_suspect,
        "yaw_residual_wrap_used": yaw_residual_wrap_used,
        "yaw_delta_rmse_raw": raw_rmse,
        "yaw_delta_rmse_after_best_wrap": wrapped_rmse,
        "n8a_reported_yaw_delta_rmse_deg": evaluation.get("yaw_delta_rmse_deg"),
        "yaw_jump_count": yaw_jump_count,
        "ekf_yaw_jump_count": ekf_jump_count,
        "ekf_wrap_boundary_pair_count": wrap_boundary_pair_count,
        "wrap_averaging_artifact_count": wrap_averaging_artifact_count,
        "transform_rmse_deg": transform_rmse,
        "initial_ekf_yaw_deg": ekf_yaw[0] if ekf_yaw else None,
        "initial_fgo_yaw_deg": fgo_yaw[0] if fgo_yaw else None,
        "final_ekf_yaw_deg": ekf_yaw[-1] if ekf_yaw else None,
        "final_fgo_yaw_deg": fgo_yaw[-1] if fgo_yaw else None,
        "smoother_weight_reported": smoother.get("smoothness_weight"),
        "blocker_status": blocker_status,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "audit_only": True,
        "solver_modified": False,
        "paper_performance_claim": False,
    }
