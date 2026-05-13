"""Build N7B4 Go2 contact confidence features.

中文说明：foot_speed_body 是足端相对机身速度，高值不能被单独解释为 swing；
本模块只输出概率模型特征，不读取 trace/final_v23 output。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _time_value
from .go2_contact_distribution import percentile, velocity_norm


FEATURE_FIELDS = [
    "time",
    "row_index",
    "foot",
    "normalized_foot_force",
    "normalized_inverse_foot_speed",
    "foot_force",
    "foot_speed_body_norm",
    "foot_speed_body_x",
    "foot_speed_body_y",
    "foot_speed_body_z",
    "foot_position_body_z",
    "mode",
    "gait_type",
    "body_height",
    "body_velocity_norm",
    "yaw_speed",
    "foot_force_derivative",
    "foot_speed_derivative",
    "force_short_window_median",
    "force_short_window_variance",
    "speed_short_window_median",
    "speed_short_window_variance",
    "foot_speed_body_interpretation",
    "trace_solver_input",
    "final_v23_output_solver_input",
    "diagnostic_only",
]


def _clamp01(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _robust_norm(value: float, low: float, high: float, *, inverse: bool = False) -> float:
    if not math.isfinite(value) or not math.isfinite(low) or not math.isfinite(high) or high <= low:
        return 0.0
    norm = _clamp01((value - low) / (high - low))
    return 1.0 - norm if inverse else norm


def _foot_vector(row: dict[str, Any], prefix: str, foot: int) -> list[float]:
    start = 3 * foot
    return [_f(row.get(f"{prefix}_{start + axis}")) for axis in range(3)]


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values)) if all(math.isfinite(value) for value in values) else math.nan


def _median(values: list[float]) -> float | None:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return None
    return finite[len(finite) // 2]


def _variance(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return None
    mean = sum(finite) / len(finite)
    return sum((value - mean) ** 2 for value in finite) / len(finite)


def _distributions(go2_rows: list[dict[str, Any]]) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    for foot in range(4):
        forces = [_f(row.get(f"foot_force_{foot}")) for row in go2_rows]
        speeds = [_norm(_foot_vector(row, "foot_speed_body", foot)) for row in go2_rows]
        out[foot] = {
            "force_p05": percentile(forces, 5) or 0.0,
            "force_p95": percentile(forces, 95) or 1.0,
            "speed_p05": percentile(speeds, 5) or 0.0,
            "speed_p95": percentile(speeds, 95) or 1.0,
        }
    return out


def build_contact_confidence_features(go2_rows: list[dict[str, Any]], *, window: int = 5) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return per-foot confidence features and a boundary report."""

    rows = sorted(go2_rows, key=_time_value)
    distributions = _distributions(rows)
    by_foot_force: dict[int, list[float]] = {foot: [] for foot in range(4)}
    by_foot_speed: dict[int, list[float]] = {foot: [] for foot in range(4)}
    for row in rows:
        for foot in range(4):
            by_foot_force[foot].append(_f(row.get(f"foot_force_{foot}")))
            by_foot_speed[foot].append(_norm(_foot_vector(row, "foot_speed_body", foot)))

    feature_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        time_value = _time_value(row)
        body_velocity = velocity_norm(row)
        for foot in range(4):
            speed_vec = _foot_vector(row, "foot_speed_body", foot)
            pos_vec = _foot_vector(row, "foot_position_body", foot)
            force = _f(row.get(f"foot_force_{foot}"))
            speed = _norm(speed_vec)
            prev_force = by_foot_force[foot][row_index - 1] if row_index > 0 else math.nan
            prev_speed = by_foot_speed[foot][row_index - 1] if row_index > 0 else math.nan
            prev_time = _time_value(rows[row_index - 1]) if row_index > 0 else math.nan
            dt = time_value - prev_time if math.isfinite(time_value) and math.isfinite(prev_time) else math.nan
            start = max(0, row_index - window // 2)
            end = min(len(rows), row_index + window // 2 + 1)
            force_window = by_foot_force[foot][start:end]
            speed_window = by_foot_speed[foot][start:end]
            dist = distributions[foot]
            feature_rows.append(
                {
                    "time": time_value,
                    "row_index": row_index,
                    "foot": foot,
                    "normalized_foot_force": _robust_norm(force, dist["force_p05"], dist["force_p95"]),
                    "normalized_inverse_foot_speed": _robust_norm(speed, dist["speed_p05"], dist["speed_p95"], inverse=True),
                    "foot_force": force,
                    "foot_speed_body_norm": speed,
                    "foot_speed_body_x": speed_vec[0],
                    "foot_speed_body_y": speed_vec[1],
                    "foot_speed_body_z": speed_vec[2],
                    "foot_position_body_z": pos_vec[2],
                    "mode": row.get("mode", ""),
                    "gait_type": row.get("gait_type", ""),
                    "body_height": _f(row.get("body_height")),
                    "body_velocity_norm": body_velocity,
                    "yaw_speed": _f(row.get("yaw_speed_radps")),
                    "foot_force_derivative": (force - prev_force) / dt if dt and math.isfinite(dt) and dt > 0 and math.isfinite(force) and math.isfinite(prev_force) else "",
                    "foot_speed_derivative": (speed - prev_speed) / dt if dt and math.isfinite(dt) and dt > 0 and math.isfinite(speed) and math.isfinite(prev_speed) else "",
                    "force_short_window_median": _median(force_window),
                    "force_short_window_variance": _variance(force_window),
                    "speed_short_window_median": _median(speed_window),
                    "speed_short_window_variance": _variance(speed_window),
                    "foot_speed_body_interpretation": "body_frame_relative_speed_not_single_swing_truth",
                    "trace_solver_input": False,
                    "final_v23_output_solver_input": False,
                    "diagnostic_only": True,
                }
            )
    report = {
        "stage": "N7B4_literature_informed_contact_velocity",
        "go2_row_count": len(rows),
        "feature_row_count": len(feature_rows),
        "feature_set": FEATURE_FIELDS,
        "normalization_source": "go2_field_distribution_only",
        "short_window_size": window,
        "foot_speed_body_interpretation": "foot_speed_body is body-frame relative speed; high value does not automatically mean swing",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_tuning": False,
        "final_v23_tuning": False,
        "diagnostic_only": True,
        "paper_performance_claim": False,
    }
    return feature_rows, report


def write_contact_confidence_features(go2_rows: list[dict[str, Any]], output_dir: str | Path) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    """Write feature CSV and report under the runtime output directory."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows, report = build_contact_confidence_features(go2_rows)
    csv_path = out / "GO2_CONTACT_CONFIDENCE_FEATURES.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FEATURE_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in FEATURE_FIELDS} for row in rows])
    report_path = out / "GO2_CONTACT_CONFIDENCE_FEATURES_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, rows, report
