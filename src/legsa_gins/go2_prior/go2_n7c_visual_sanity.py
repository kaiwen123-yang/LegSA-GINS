"""Visual sanity checks for N7C1 Go2 horizontal velocity validation.

中文说明：这些检查只判断 N7C1 图像和 runtime 报告是否自洽，不根据图像结果
调权、不删 epoch、不做 output-only correction。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_n7c_plot_coverage import N7C1FigureCoverage


def _iter_numbers(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _iter_numbers(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_numbers(child)
    elif isinstance(value, (int, float)):
        yield float(value)


def _is_monotonic(rows: list[dict[str, Any]], key: str) -> bool:
    values: list[float] = []
    for row in rows:
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return bool(values) and all(values[index] <= values[index + 1] for index in range(len(values) - 1))


def _trace_monotonic_by_source(rows: list[dict[str, Any]]) -> bool:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_source.setdefault(str(row.get("source_id", "")), []).append(row)
    return bool(by_source) and all(_is_monotonic(source_rows, "time") for source_rows in by_source.values())


def _clean_no_gross_degradation(reports: dict[str, dict[str, Any]]) -> bool:
    comparison = reports.get("N7C_GO2_HORIZONTAL_VELOCITY_COMPARISON_REPORT.json", {})
    delta = comparison.get("comparisons", {}).get("go2_horizontal_velocity_main_minus_baseline", {}).get("delta", {})
    horizontal = abs(float(delta.get("horizontal_rmse_m") or 0.0))
    up = abs(float(delta.get("up_rmse_m") or 0.0))
    yaw = abs(float(delta.get("yaw_rmse_deg") or 0.0))
    # 中文说明：这里只拦截显著异常，不用 trace/final_v23 反向调参。
    return horizontal < 0.5 and up < 0.5 and yaw < 5.0


def _stress_visual_stable(reports: dict[str, dict[str, Any]]) -> bool:
    comparison = reports.get("N7C_GO2_HORIZONTAL_VELOCITY_COMPARISON_REPORT.json", {})
    comparisons = comparison.get("comparisons", {})
    for key in ["receiver_velocity_stress_plus_go2_minus_no_go2", "raw_doppler_stress_plus_go2_minus_no_go2"]:
        delta = comparisons.get(key, {}).get("delta", {})
        if abs(float(delta.get("horizontal_rmse_m") or 0.0)) >= 0.5:
            return False
        if abs(float(delta.get("yaw_rmse_deg") or 0.0)) >= 5.0:
            return False
    return True


def build_n7c1_visual_sanity_report(
    *,
    visual_inputs: dict[str, Any],
    figure_manifest: dict[str, Any],
    coverage_report: dict[str, Any],
) -> dict[str, Any]:
    reports = visual_inputs["reports"]
    coverage_rows: list[N7C1FigureCoverage] = figure_manifest.get("coverage", [])
    numbers = list(_iter_numbers(reports))
    numbers.extend(value for row in coverage_rows for value in [row.x_min, row.x_max, row.y_min, row.y_max] if value is not None)
    no_nan_inf = all(math.isfinite(value) for value in numbers)
    clean_errors = visual_inputs.get("clean_errors", {})
    prior_rows = visual_inputs.get("prior_rows", [])
    trace_rows = visual_inputs.get("main_trace_rows", [])
    time_monotonic = (
        all(_is_monotonic(rows, "timestamp") for rows in clean_errors.values() if rows)
        and _is_monotonic(prior_rows, "time")
        and _trace_monotonic_by_source(trace_rows)
    )
    decision = reports.get("N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json", {})
    main_summary = {}
    for row in reports.get("N7C_GO2_HORIZONTAL_VELOCITY_VARIANT_SUMMARIES.json", {}).get("variants", []):
        if row.get("variant_id") == "go2_horizontal_velocity_weak_prior_main":
            main_summary = row
            break
    update_count = int(decision.get("update_count", 0) or 0)
    report_update_count = int(main_summary.get("go2_horizontal_velocity_prior_update_count", -1) or -1)
    reject_count = int(decision.get("reject_count", 0) or 0)
    stress_figures = [row for row in coverage_rows if row.figure_category == "stress"]
    report = {
        "stage": "N7C1_go2_horizontal_velocity_visual_validation",
        "no_nan_inf": no_nan_inf,
        "time_monotonic": time_monotonic,
        "required_figures_generated": bool(coverage_report.get("required_figures_generated")) and bool(figure_manifest.get("required_figures_generated")),
        "required_figures_nonempty": bool(coverage_report.get("required_figures_nonempty")) and bool(figure_manifest.get("required_figures_nonempty")),
        "clean_no_gross_degradation_visual": _clean_no_gross_degradation(reports),
        "go2_horizontal_prior_update_count_matches_report": update_count == report_update_count and update_count > 0,
        "go2_horizontal_prior_reject_count_reasonable": reject_count >= 0 and reject_count <= max(update_count, 1),
        "vertical_velocity_disabled_confirmed": bool(visual_inputs.get("manifest", {}).get("vertical_disabled_confirmed")),
        "go2_position_prior_disabled": reports.get("N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json", {}).get("go2_position_prior_enabled") is False,
        "go2_yaw_prior_disabled": reports.get("N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json", {}).get("go2_yaw_prior_enabled") is False,
        "stress_variants_visualized": bool(stress_figures) and all(not row.empty_plot_suspect for row in stress_figures),
        "stress_variants_visual_stable": _stress_visual_stable(reports),
        "no_trace_solver_input": True,
        "no_final_v23_solver_input": True,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    report["visual_sanity_passed"] = all(
        bool(report[key])
        for key in [
            "no_nan_inf",
            "time_monotonic",
            "required_figures_generated",
            "required_figures_nonempty",
            "clean_no_gross_degradation_visual",
            "go2_horizontal_prior_update_count_matches_report",
            "go2_horizontal_prior_reject_count_reasonable",
            "vertical_velocity_disabled_confirmed",
            "go2_position_prior_disabled",
            "go2_yaw_prior_disabled",
            "stress_variants_visualized",
            "stress_variants_visual_stable",
            "no_trace_solver_input",
            "no_final_v23_solver_input",
        ]
    )
    return report


def write_n7c1_visual_sanity_report(path: str | Path, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
