"""N4H4D5 one-step propagation parity diagnostics.

中文说明：external clean state 只作为 shadow diagnostic seed，不进入 LegSA solver。
这里使用标准库轻量 one-step kinematic proxy，无法替代正式 mechanization fix。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .legsa_v23_external_trace_parity import parse_nav


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {"count": 0, "median": None, "p95": None, "max": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "median": ordered[len(ordered) // 2],
        "p95": ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))],
        "max": max(clean),
    }


def _wrap_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _horizontal_step_error(prev: dict[str, float], curr: dict[str, float]) -> float:
    dt = curr["time"] - prev["time"]
    if dt <= 0.0:
        return 0.0
    lat_m = (curr["lat_deg"] - prev["lat_deg"]) * 111_319.49079327358
    lon_m = (curr["lon_deg"] - prev["lon_deg"]) * 111_319.49079327358 * math.cos(math.radians(prev["lat_deg"]))
    pred_n = prev.get("vn", 0.0) * dt
    pred_e = prev.get("ve", 0.0) * dt
    return math.hypot(lat_m - pred_n, lon_m - pred_e)


def run_one_step_propagation_parity(
    external_nav: str | Path,
    clean_imu: str | Path | None = None,
    selected_times: list[float] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """中文说明：离线检查相邻 external clean 状态的一步传播 proxy 是否异常。"""

    rows = parse_nav(external_nav)
    if len(rows) < 2:
        return {
            "status": "evidence_missing",
            "one_step_mechanization_ok": False,
            "one_step_mechanization_suspect": False,
            "shadow_external_nav_solver_input": False,
            "trace_solver_input": False,
            "numerical_performance_claim": False,
        }
    if selected_times:
        selected = []
        for time in selected_times:
            closest = min(range(len(rows) - 1), key=lambda index: abs(rows[index]["time"] - time))
            selected.append((rows[closest], rows[closest + 1]))
    else:
        step = max(1, (len(rows) - 1) // 10)
        selected = [(rows[index], rows[index + 1]) for index in range(0, len(rows) - 1, step)][:20]
    h_errors = [_horizontal_step_error(prev, curr) for prev, curr in selected]
    v_errors = [
        math.sqrt(
            (curr.get("vn", 0.0) - prev.get("vn", 0.0)) ** 2
            + (curr.get("ve", 0.0) - prev.get("ve", 0.0)) ** 2
            + (curr.get("vd", 0.0) - prev.get("vd", 0.0)) ** 2
        )
        for prev, curr in selected
    ]
    att_errors = [
        math.sqrt(
            _wrap_deg(curr.get("roll_deg", 0.0) - prev.get("roll_deg", 0.0)) ** 2
            + _wrap_deg(curr.get("pitch_deg", 0.0) - prev.get("pitch_deg", 0.0)) ** 2
            + _wrap_deg(curr.get("yaw_deg", 0.0) - prev.get("yaw_deg", 0.0)) ** 2
        )
        for prev, curr in selected
    ]
    h_stats = _stats(h_errors)
    v_stats = _stats(v_errors)
    att_stats = _stats(att_errors)
    ok = bool((h_stats["median"] or 999.0) < 0.05 and (att_stats["median"] or 999.0) < 0.2)
    suspect = bool((att_stats["median"] or 0.0) > 1.0 or (v_stats["median"] or 0.0) > 0.5)
    return {
        "status": "analyzed",
        "sample_count": len(selected),
        "median_horizontal_step_error_m": h_stats["median"],
        "median_velocity_step_error_mps": v_stats["median"],
        "median_attitude_step_error_deg": att_stats["median"],
        "horizontal_step_error_stats": h_stats,
        "velocity_step_error_stats": v_stats,
        "attitude_step_error_stats": att_stats,
        "one_step_mechanization_ok": ok,
        "one_step_mechanization_suspect": suspect,
        "external_state_diagnostic_seed_only": True,
        "shadow_external_nav_solver_input": False,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
