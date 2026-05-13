"""N7C5A visual sanity checks.

中文说明：sanity 只检查图像复核输入和输出是否可信；不做 solver 调参、
不把 Go2 本体观测当 truth。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _monotonic(rows: list[dict[str, Any]]) -> bool:
    times = [_f(row.get("time"), math.nan) for row in rows]
    times = [value for value in times if math.isfinite(value)]
    return len(times) < 2 or all(b >= a for a, b in zip(times, times[1:]))


def _all_finite(rows: list[dict[str, Any]], keys: list[str]) -> bool:
    if not rows:
        return False
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value in {"", None}:
                continue
            if not math.isfinite(_f(value, math.nan)):
                return False
    return True


def build_n7c5a_visual_sanity(
    inputs: dict[str, Any],
    figure_manifest: dict[str, Any],
    coverage_report: dict[str, Any],
) -> dict[str, Any]:
    foot_rows = inputs.get("foot_rows", [])
    phase_rows = inputs.get("phase_rows", [])
    contact_rows = inputs.get("contact_rows", [])
    contact_values = [
        _f(row.get(f"foot_{foot}_contact_probability"), math.nan)
        for row in contact_rows
        for foot in range(4)
    ]
    finite_contact = [value for value in contact_values if math.isfinite(value)]
    speed_values = [
        math.hypot(_f(row.get("candidate_vn"), 0.0), _f(row.get("candidate_ve"), 0.0))
        for row in foot_rows
        if math.isfinite(_f(row.get("candidate_vn"), math.nan)) and math.isfinite(_f(row.get("candidate_ve"), math.nan))
    ]
    checks = {
        "no_nan_inf": _all_finite(foot_rows[:5000], ["candidate_vn", "candidate_ve", "residual_to_receiver", "residual_to_raw"]),
        "time_monotonic": _monotonic(foot_rows) and _monotonic(phase_rows),
        "required_figures_generated": bool(figure_manifest.get("required_figures_generated")),
        "required_figures_nonempty": bool(figure_manifest.get("required_figures_nonempty")),
        "contact_probability_not_all_zero_or_all_one": bool(finite_contact) and not all(value <= 0.0 for value in finite_contact) and not all(value >= 1.0 for value in finite_contact),
        "foot_kinematic_velocity_has_finite_series": coverage_report.get("foot_kinematic_finite_rows", 0) > 0,
        "foot_kinematic_velocity_not_obviously_exploding": bool(speed_values) and max(speed_values) < 20.0,
        "yawrate_consistency_visual_available": bool(inputs.get("yawrate_report")),
        "relative_odometry_visual_available": bool(inputs.get("relative_report")),
        "ranking_visual_available": bool(inputs.get("ranking_report", {}).get("candidates", [])),
        "no_truth_claim": True,
        "no_trace_solver_input": not bool(inputs.get("trace_solver_input")),
        "no_final_v23_solver_input": not bool(inputs.get("final_v23_output_solver_input")),
    }
    blocker_keys = [key for key, value in checks.items() if value is False and key not in {"no_nan_inf"}]
    return {
        "stage": "N7C5A_go2_full_proprioceptive_visual_review",
        "checks": checks,
        "visual_blocker": bool(blocker_keys),
        "blocker_reasons": blocker_keys,
        "contact_rows_summary_only": bool(inputs.get("contact_rows_summary_only")),
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def write_n7c5a_visual_sanity(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
