"""Sanity checks for N4H4E visual validation.

中文说明：visual_candidate_passed 只是工程图像候选通过，不是 paper
performance claim，不代表 outperform final_v23。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.visualization.legsa_v23_port_visual_plots import REQUIRED_FIGURE_NAMES


def _numeric_values(value: Any) -> list[float]:
    if isinstance(value, dict):
        values: list[float] = []
        for item in value.values():
            values.extend(_numeric_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_numeric_values(item))
        return values
    if isinstance(value, (int, float)):
        return [float(value)]
    return []


def check_time_monotonic(rows: list[dict[str, Any]]) -> bool:
    previous: float | None = None
    for row in rows:
        current = float(row.get("timestamp", row.get("time", 0.0)))
        if previous is not None and current < previous:
            return False
        previous = current
    return True


def yaw_wrap_spike_detected(errors: list[dict[str, Any]], threshold_deg: float = 90.0) -> bool:
    yaws = [float(row.get("yaw_error_deg", 0.0)) for row in errors]
    if len(yaws) < 2:
        return False
    jumps = [abs(yaws[index] - yaws[index - 1]) for index in range(1, len(yaws))]
    return max(jumps) > threshold_deg


def required_figures_generated(figure_root: str | Path, required: list[str] | None = None) -> dict[str, Any]:
    root = Path(figure_root)
    names = required or REQUIRED_FIGURE_NAMES
    missing = [name for name in names if not (root / name).exists()]
    return {
        "required_figures": names,
        "missing_required_figures": missing,
        "required_figures_generated": not missing,
    }


def build_visual_sanity_report(
    *,
    inputs: dict[str, Any],
    plot_report: dict[str, Any],
    figure_output_dir: str | Path,
    aligned_count_minimum: int = 50000,
    figure_count_minimum: int = 30,
) -> dict[str, Any]:
    port_errors = plot_report["errors"]["port_vs_trace"]
    final_errors = plot_report["errors"]["final_v23_vs_trace"]
    parity_errors = plot_report["errors"]["port_vs_final_v23"]
    finite = all(math.isfinite(value) for value in _numeric_values([inputs["port_rows"], inputs["final_v23_rows"], inputs["trace_rows"], port_errors, final_errors, parity_errors]))
    max_h = max([abs(row["horizontal_error_m"]) for row in port_errors] or [0.0])
    max_up = max([abs(row["up_error_m"]) for row in port_errors] or [0.0])
    max_yaw = max([abs(row["yaw_error_deg"]) for row in port_errors] or [0.0])
    max_roll_pitch = max(
        [abs(row["roll_error_deg"]) for row in port_errors] + [abs(row["pitch_error_deg"]) for row in port_errors] or [0.0]
    )
    required = required_figures_generated(figure_output_dir)
    comparison = inputs["r3c_reports"].get("PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json", {})
    parity_report = inputs["r3c_reports"].get("PORT_VS_FINALV23_NAV_PARITY_REPORT.json", {})
    final_abs = inputs["r3c_reports"].get("FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json", {})
    no_gross_trajectory_discontinuity = max_h <= 5.0 and max_up <= 5.0
    report = {
        "phase": "N4H4E",
        "time_monotonic": bool(
            check_time_monotonic(inputs["port_rows"])
            and check_time_monotonic(inputs["final_v23_rows"])
            and check_time_monotonic(inputs["trace_rows"])
        ),
        "no_nan_inf": finite,
        "aligned_count": len(parity_errors),
        "aligned_count_minimum": aligned_count_minimum,
        "aligned_count_ok": len(parity_errors) >= aligned_count_minimum,
        "port_finalv23_parity_small": bool(parity_report.get("parity_small")),
        "finalv23_absolute_reproduced": bool(final_abs.get("official_summary_reproduced")),
        "port_absolute_close_to_finalv23_absolute": bool(comparison.get("port_absolute_close_to_finalv23_absolute")),
        "yaw_wrap_spike_detected": yaw_wrap_spike_detected(port_errors),
        "horizontal_error_max_m": max_h,
        "horizontal_error_max_reasonable": max_h <= 5.0,
        "up_error_max_m": max_up,
        "up_error_max_reasonable": max_up <= 5.0,
        "yaw_error_abs_max_deg": max_yaw,
        "yaw_error_abs_max_reasonable": max_yaw <= 20.0,
        "roll_pitch_abs_max_deg": max_roll_pitch,
        "roll_pitch_abs_max_reasonable": max_roll_pitch <= 12.0,
        "figure_count_total": int(plot_report.get("figure_count_total", 0)),
        "figure_count_minimum": figure_count_minimum,
        "figure_count_minimum_ok": int(plot_report.get("figure_count_total", 0)) >= figure_count_minimum,
        "required_figures_generated": required["required_figures_generated"],
        "missing_required_figures": required["missing_required_figures"],
        "pure_single_comparison_absent": bool(plot_report.get("pure_single_comparison_absent")),
        "no_gross_trajectory_discontinuity_detected": no_gross_trajectory_discontinuity,
        "visual_manual_review_required": True,
        "manual_visual_review_required": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    report["visual_candidate_passed"] = bool(
        report["time_monotonic"]
        and report["no_nan_inf"]
        and report["required_figures_generated"]
        and report["figure_count_minimum_ok"]
        and report["aligned_count_ok"]
        and report["port_finalv23_parity_small"]
        and report["finalv23_absolute_reproduced"]
        and report["port_absolute_close_to_finalv23_absolute"]
        and not report["yaw_wrap_spike_detected"]
        and report["no_gross_trajectory_discontinuity_detected"]
    )
    report["blocking_issues"] = [
        name
        for name, ok in [
            ("time_not_monotonic", report["time_monotonic"]),
            ("nan_or_inf_detected", report["no_nan_inf"]),
            ("required_figures_missing", report["required_figures_generated"]),
            ("figure_count_below_minimum", report["figure_count_minimum_ok"]),
            ("aligned_count_below_minimum", report["aligned_count_ok"]),
            ("port_finalv23_parity_not_small", report["port_finalv23_parity_small"]),
            ("finalv23_absolute_not_reproduced", report["finalv23_absolute_reproduced"]),
            ("port_absolute_not_close_to_finalv23_absolute", report["port_absolute_close_to_finalv23_absolute"]),
            ("gross_trajectory_discontinuity_detected", report["no_gross_trajectory_discontinuity_detected"]),
        ]
        if not ok
    ]
    if report["yaw_wrap_spike_detected"]:
        report["blocking_issues"].append("yaw_wrap_spike_detected")
    return report


def write_visual_sanity_report(path: str | Path, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
