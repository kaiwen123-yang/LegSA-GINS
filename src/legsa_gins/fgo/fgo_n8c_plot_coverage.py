"""N8C mandatory plot data coverage checks.

中文说明：记录每张图实际绘制的数据量，防止空图或只有装饰性图像。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MANDATORY_N8C_FIGURES = [
    "ekf_vs_fgo_weak_yaw_horizontal_trajectory.png",
    "fgo_minus_ekf_horizontal_diff_time.png",
    "ekf_vs_fgo_weak_yaw_horizontal_error.png",
    "ekf_vs_fgo_weak_yaw_up_error.png",
    "ekf_vs_fgo_weak_yaw_yaw_error.png",
    "ekf_vs_fgo_weak_yaw_roll_pitch_error.png",
    "default_vs_weak_yaw_fgo_yaw_time.png",
    "default_vs_weak_yaw_delta_time.png",
    "weak_yaw_smoothness_residual_time.png",
    "per_factor_residual_p95_bar.png",
    "receiver_position_residual_time.png",
    "receiver_velocity_residual_time.png",
    "dual_yaw_residual_time.png",
    "raw_doppler_residual_time.png",
    "go2_joint_factor_residual_time.png",
    "smoothness_factor_residual_time.png",
    "factor_on_off_metric_delta_bar.png",
    "go2_joint_on_off_delta_time.png",
    "raw_doppler_on_off_delta_time.png",
    "candidate_factor_diagnostic_delta_bar.png",
    "n8c_visual_decision_panel.png",
    "n8c_metric_summary_panel.png",
]


def monotonic(values: list[float]) -> bool:
    return all(right >= left for left, right in zip(values, values[1:]))


def coverage_entry(
    *,
    figure_name: str,
    series: list[list[float]],
    x_values: list[float] | None = None,
    figure_path: str | Path | None = None,
    aggregate_only: bool = False,
    diagnostic_candidate_label: bool = False,
) -> dict[str, Any]:
    rows = [len(row) for row in series]
    flat = [float(value) for row in series for value in row if value == value]
    x = [float(value) for value in (x_values or []) if value == value]
    x_range = (max(x) - min(x)) if x else float(max(rows) if rows else 0)
    y_range = (max(flat) - min(flat)) if flat else 0.0
    path = Path(figure_path) if figure_path else None
    nonempty = bool(path and path.exists() and path.stat().st_size > 0)
    reason_codes: list[str] = []
    if not rows or max(rows) <= 0:
        reason_codes.append("no_plotted_rows")
    if x and not monotonic(x):
        reason_codes.append("time_not_monotonic")
    if x and x_range < 200.0 and not aggregate_only:
        reason_codes.append("time_span_lt_200s")
    if not nonempty:
        reason_codes.append("figure_empty_or_missing")
    return {
        "figure_name": figure_name,
        "plotted_series_count": len(series),
        "rows_per_series": rows,
        "x_range": x_range,
        "y_range": y_range,
        "nonempty": nonempty,
        "time_monotonic": monotonic(x) if x else True,
        "empty_plot_suspect": "no_plotted_rows" in reason_codes or "figure_empty_or_missing" in reason_codes,
        "aggregate_only": aggregate_only,
        "candidate_diagnostic_only_label": diagnostic_candidate_label,
        "reason_codes": reason_codes,
    }


def build_plot_coverage_report(entries: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {entry["figure_name"]: entry for entry in entries}
    missing = [name for name in MANDATORY_N8C_FIGURES if name not in by_name]
    failed = [
        entry["figure_name"]
        for entry in entries
        if entry.get("empty_plot_suspect") or not entry.get("nonempty") or (entry.get("reason_codes") and not entry.get("aggregate_only"))
    ]
    return {
        "stage": "N8C_no_feedback_fgo_visual_validation",
        "mandatory_figure_count": len(MANDATORY_N8C_FIGURES),
        "coverage_entries": entries,
        "missing_figures": missing,
        "failed_figures": failed,
        "all_mandatory_figures_present": not missing,
        "all_mandatory_figures_nonempty": all(entry.get("nonempty") for entry in entries) and not missing,
        "visual_validation_passed": not missing and not failed,
        "candidate_plots_diagnostic_only_labeled": all(
            entry.get("candidate_diagnostic_only_label", True)
            for entry in entries
            if "candidate" in str(entry.get("figure_name", ""))
        ),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
    }


def write_plot_coverage_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
