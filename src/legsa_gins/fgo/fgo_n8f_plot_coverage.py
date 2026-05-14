"""N8F1 plot data coverage checks.

中文说明：覆盖率审查只检查图像背后的绘图数据是否非空、轴范围是否合理。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


MANDATORY_N8F1_FIGURES = [
    "01_contact_weighting/contact_weight_scale_time.png",
    "01_contact_weighting/support_confidence_slip_risk_time.png",
    "01_contact_weighting/contact_weight_histogram.png",
    "02_foot_kinematic/foot_kinematic_velocity_components_time.png",
    "02_foot_kinematic/foot_kinematic_velocity_vs_go2_velocity.png",
    "02_foot_kinematic/foot_kinematic_velocity_residual_time.png",
    "02_foot_kinematic/foot_kinematic_whitened_residual_time.png",
    "02_foot_kinematic/foot_kinematic_factor_toggle_delta.png",
    "03_yawrate_between/yawrate_between_residual_time.png",
    "03_yawrate_between/yawrate_between_wrapped_delta_time.png",
    "03_yawrate_between/yawrate_between_factor_toggle_delta.png",
    "04_relative_odometry/relative_odometry_residual_time.png",
    "04_relative_odometry/relative_odometry_delta_components.png",
    "04_relative_odometry/relative_odometry_factor_toggle_delta.png",
    "05_candidate_stack/candidate_stack_variant_delta_bar.png",
    "05_candidate_stack/candidate_factor_whitened_residual_p95_bar.png",
    "05_candidate_stack/candidate_factor_rows_and_jacobian_bar.png",
    "06_solver_effect/legged_candidate_stack_horizontal_delta_time.png",
    "06_solver_effect/legged_candidate_stack_yaw_delta_time.png",
    "06_solver_effect/legged_candidate_stack_roll_pitch_delta_bar.png",
    "06_solver_effect/gross_degradation_check_panel.png",
    "07_summary/n8f1_visual_decision_panel.png",
    "07_summary/n8f1_factor_status_summary.png",
]


def build_series_coverage(
    *,
    figure_name: str,
    series: Sequence[Mapping[str, Any]],
    x_key: str = "time",
    y_key: str = "value",
    reason_codes: Sequence[str] | None = None,
) -> Dict[str, Any]:
    xs = [float(row.get(x_key, index) or 0.0) for index, row in enumerate(series)]
    ys = [float(row.get(y_key, 0.0) or 0.0) for row in series]
    x_range = (max(xs) - min(xs)) if xs else 0.0
    y_range = (max(ys) - min(ys)) if ys else 0.0
    has_data = bool(series)
    return {
        "figure_name": figure_name,
        "plotted_series_count": 1 if has_data else 0,
        "plotted_row_count_by_series": {"primary": len(series)},
        "total_plotted_row_count": len(series),
        "x_min": min(xs) if xs else None,
        "x_max": max(xs) if xs else None,
        "x_range": x_range,
        "y_min": min(ys) if ys else None,
        "y_max": max(ys) if ys else None,
        "y_range": y_range,
        "has_nonempty_data": has_data,
        "has_reasonable_time_axis": has_data and x_range >= 0.0,
        "empty_plot_suspect": not has_data,
        "reason_codes": list(reason_codes or []),
    }


def build_n8f1_plot_coverage_report(
    *,
    figure_manifest: Mapping[str, Any],
    coverage_rows: Sequence[Mapping[str, Any]],
    n8f_reports: Mapping[str, Any],
) -> Dict[str, Any]:
    coverage_by_name = {str(row.get("figure_name")): dict(row) for row in coverage_rows}
    missing = [name for name in MANDATORY_N8F1_FIGURES if name not in coverage_by_name]
    contact_rows = int(n8f_reports.get("contact_weighting", {}).get("rows", 0) or 0)
    foot_residual_rows = int(n8f_reports.get("foot_kinematic", {}).get("residual_rows", 0) or 0)
    yaw_residual_rows = int(n8f_reports.get("yawrate", {}).get("residual_rows", 0) or 0)
    relative_residual_rows = int(n8f_reports.get("relative_odometry", {}).get("residual_rows", 0) or 0)
    blockers = []
    if missing:
        blockers.append("coverage_missing_for_mandatory_figures")
    if contact_rows >= 500 and any(
        coverage_by_name.get(name, {}).get("total_plotted_row_count", 0) < 500
        for name in MANDATORY_N8F1_FIGURES[:3]
    ):
        blockers.append("contact_weighting_plot_rows_below_500")
    if foot_residual_rows <= 0:
        blockers.append("foot_residual_rows_missing")
    if yaw_residual_rows <= 0:
        blockers.append("yawrate_residual_rows_missing")
    if relative_residual_rows <= 0:
        blockers.append("relative_odometry_residual_rows_missing")
    if not figure_manifest.get("required_figures_nonempty"):
        blockers.append("figures_missing_or_empty")
    visual_passed = not blockers and all(bool(row.get("has_nonempty_data")) for row in coverage_rows)
    return {
        "stage": "N8F1",
        "mandatory_figure_count": len(MANDATORY_N8F1_FIGURES),
        "coverage_rows": list(coverage_rows),
        "coverage_missing": missing,
        "coverage_blockers": blockers,
        "contact_weighting_rows_expected": contact_rows,
        "foot_residual_rows_expected": foot_residual_rows,
        "yawrate_residual_rows_expected": yaw_residual_rows,
        "relative_odometry_residual_rows_expected": relative_residual_rows,
        "visual_validation_passed": visual_passed,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
        "go2_truth_claim": False,
    }


def write_plot_coverage_report(path: str | Path, report: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output

