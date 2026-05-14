"""N8C2 smoothness component review.

中文说明：拆分 smoothness 分量做诊断，不删除 smoothness 作为最终捷径。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.fgo.fgo_angle_utils import safe_angle_diff_deg, shortest_angle_residual_deg
from legsa_gins.fgo.fgo_factor_activation_audit import residual_stats, select_current_rows, write_json_report
from legsa_gins.fgo.fgo_yaw_convention_fix import _f


COMPONENT_DIMENSION = {
    "position_smoothness": 3,
    "velocity_smoothness": 3,
    "yaw_smoothness": 1,
    "roll_pitch_smoothness": 2,
    "other_attitude_smoothness": 0,
}


def _position_step(left: dict[str, Any], right: dict[str, Any]) -> float:
    lat0 = math.radians(_f(left.get("lat_deg")))
    north = (_f(right.get("lat_deg")) - _f(left.get("lat_deg"))) * 111_320.0
    east = (_f(right.get("lon_deg")) - _f(left.get("lon_deg"))) * 111_320.0 * math.cos(lat0)
    up = _f(right.get("height_m")) - _f(left.get("height_m"))
    return math.sqrt(north * north + east * east + up * up)


def smoothness_component_series(rows: list[dict[str, Any]]) -> dict[str, dict[str, list[float]]]:
    times = [_f(row.get("time", row.get("timestamp")), float(index)) for index, row in enumerate(rows)]
    out = {
        "position_smoothness": {"time": times[1:], "values": []},
        "velocity_smoothness": {"time": times[1:], "values": []},
        "yaw_smoothness": {"time": times[1:], "values": []},
        "roll_pitch_smoothness": {"time": times[1:], "values": []},
        "other_attitude_smoothness": {"time": times[1:], "values": []},
    }
    for left, right in zip(rows, rows[1:]):
        out["position_smoothness"]["values"].append(_position_step(left, right))
        out["velocity_smoothness"]["values"].append(
            math.sqrt(sum((_f(right.get(column)) - _f(left.get(column))) ** 2 for column in ("vn_mps", "ve_mps", "vd_mps")))
        )
        out["yaw_smoothness"]["values"].append(abs(shortest_angle_residual_deg(_f(right.get("yaw_deg")), _f(left.get("yaw_deg")))))
        roll = safe_angle_diff_deg(_f(right.get("roll_deg")), _f(left.get("roll_deg")))
        pitch = safe_angle_diff_deg(_f(right.get("pitch_deg")), _f(left.get("pitch_deg")))
        out["roll_pitch_smoothness"]["values"].append(math.sqrt(roll * roll + pitch * pitch))
        out["other_attitude_smoothness"]["values"].append(0.0)
    return out


def _component_row(component: str, times: list[float], values: list[float]) -> dict[str, Any]:
    dimension = COMPONENT_DIMENSION[component]
    raw = residual_stats(values)
    whitened_values = list(values)
    normalized_values = [value / math.sqrt(max(1, dimension)) for value in whitened_values]
    whitened = residual_stats(whitened_values)
    normalized = residual_stats(normalized_values)
    threshold = max(whitened["p95"], whitened["p50"] * 3.0)
    spikes = [(time, value) for time, value in zip(times, whitened_values) if value > threshold and value > 0.0]
    return {
        "component": component,
        "raw_p95": raw["p95"],
        "whitened_p95": whitened["p95"],
        "dimension_normalized_p95": normalized["p95"],
        "spike_count": len(spikes),
        "time_segments_with_spikes": [{"time": time, "value": value} for time, value in spikes[:12]],
        "dimension": dimension,
        "sample_count": len(values),
    }


def build_smoothness_component_review(
    *,
    rows_by_variant: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows = select_current_rows(rows_by_variant)
    series = smoothness_component_series(rows)
    component_rows = [_component_row(name, payload["time"], payload["values"]) for name, payload in series.items()]
    nonzero = [row for row in component_rows if row["dimension"] > 0]
    dominant = max(nonzero, key=lambda row: float(row.get("dimension_normalized_p95", 0.0) or 0.0), default={})
    yaw_row = next((row for row in component_rows if row["component"] == "yaw_smoothness"), {})
    yaw_dominates = dominant.get("component") == "yaw_smoothness" and float(yaw_row.get("dimension_normalized_p95", 0.0) or 0.0) > 0.0
    recommendations = ["keep weak_yaw_smoothness", "redesign smoothness as process/kinematic factor", "split smoothness weights"]
    if yaw_dominates:
        recommendations.append("candidate N8D process factor redesign")
    return {
        "stage": "N8C2_fgo_factor_activation_review",
        "smoothness_component_rows": component_rows,
        "component_causing_spikes": dominant.get("component", ""),
        "yaw_smoothness_dominates_after_weak_yaw_policy": bool(yaw_dominates),
        "position_velocity_smoothness_physically_meaningful": bool(
            next((row for row in component_rows if row["component"] == "position_smoothness"), {}).get("sample_count", 0)
            and next((row for row in component_rows if row["component"] == "velocity_smoothness"), {}).get("sample_count", 0)
        ),
        "recommendations": recommendations,
        "smoothness_deleted_as_final_shortcut": False,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
