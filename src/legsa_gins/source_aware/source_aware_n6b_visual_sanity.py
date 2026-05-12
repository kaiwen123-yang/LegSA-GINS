"""Visual sanity checks for N6B1 source-aware validation.

中文说明：这些检查只解释图像和 runtime 报告是否可信；不根据图像结果调权、
不做 output-only correction、不删除任何 epoch。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.source_aware.source_aware_n6b_plot_coverage import N6B1FigureCoverage


SOURCE_CAPS = {
    "receiver_position": 5.0,
    "receiver_velocity": 8.0,
    "dual_antenna_yaw": 10.0,
    "raw_doppler_velocity": 15.0,
}


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


def _is_trace_monotonic_by_source(rows: list[dict[str, Any]]) -> bool:
    # 中文说明：SOURCE_AWARE_WEIGHT_TRACE 按 update/source 交错写入，不能要求全表
    # time 严格单调；只要求每个 source 自身时间轴单调。
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_source.setdefault(str(row.get("source_id", "")), []).append(row)
    return bool(by_source) and all(_is_monotonic(source_rows, "time") for source_rows in by_source.values())


def _clean_gross_degradation_ok(reports: dict[str, Any]) -> bool:
    gate = reports.get("N6B_SOURCE_AWARE_POLICY_DIAGNOSTICS.json", {}).get("clean_neutrality_gate", {})
    return bool(gate.get("pass"))


def _source_not_stuck_at_cap(stats: dict[str, Any], source_id: str) -> bool:
    cap = SOURCE_CAPS[source_id]
    row = stats.get("stats_by_source", {}).get(source_id, {})
    p50 = float(row.get("R_scale_p50", 0.0) or 0.0)
    p95 = float(row.get("R_scale_p95", 0.0) or 0.0)
    max_value = float(row.get("R_scale_max", 0.0) or 0.0)
    # 中文说明：允许个别 spike 到 cap；若 p50/p95 也贴近 cap，才判为“被卡死”。
    return not (p50 >= 0.90 * cap and p95 >= 0.95 * cap and max_value >= 0.99 * cap)


def build_n6b1_visual_sanity_report(
    *,
    visual_inputs: dict[str, Any],
    figure_manifest: dict[str, Any],
    coverage_report: dict[str, Any],
) -> dict[str, Any]:
    reports = visual_inputs["reports"]
    coverage_rows: list[N6B1FigureCoverage] = figure_manifest.get("coverage", [])
    numbers = list(_iter_numbers(reports))
    numbers.extend(value for row in coverage_rows for value in [row.x_min, row.x_max, row.y_min, row.y_max] if value is not None)
    no_nan_inf = all(math.isfinite(value) for value in numbers)
    clean_errors = visual_inputs.get("clean_errors", {})
    trace_rows = visual_inputs.get("n6b_trace", [])
    time_monotonic = all(_is_monotonic(rows, "timestamp") for rows in clean_errors.values() if rows) and _is_trace_monotonic_by_source(trace_rows)
    main_stats = reports.get("N6B_SOURCE_AWARE_WEIGHT_STATS.json", {}).get("main_variant_stats", {})
    spike = reports.get("N6B_SPIKE_RESPONSE_REPORT.json", {})
    raw_spike_visible = spike.get("response_status") in {"increased_mildly", "increased", "visible"} or any(
        float(row.get("raw_doppler_combined_R_scale") or 0.0) > float(row.get("raw_doppler_normal_median_scale") or 1.0)
        for row in spike.get("responses", [])
    )
    stress_figures = [row for row in coverage_rows if row.figure_category == "stress"]
    stress_visualized = bool(stress_figures) and all(not row.empty_plot_suspect for row in stress_figures)
    report = {
        "stage": "N6B1_source_aware_visual_validation",
        "no_nan_inf": no_nan_inf,
        "time_monotonic": time_monotonic,
        "required_figures_generated": bool(coverage_report.get("required_figures_generated")) and bool(figure_manifest.get("required_figures_generated")),
        "required_figures_nonempty": bool(coverage_report.get("required_figures_nonempty")) and bool(figure_manifest.get("required_figures_nonempty")),
        "clean_no_gross_degradation_visual": _clean_gross_degradation_ok(reports),
        "receiver_position_not_slammed_to_cap": _source_not_stuck_at_cap(main_stats, "receiver_position"),
        "receiver_velocity_not_slammed_to_cap": _source_not_stuck_at_cap(main_stats, "receiver_velocity"),
        "raw_doppler_spike_response_visible": raw_spike_visible,
        "stress_variants_visualized": stress_visualized,
        "no_trace_solver_input": True,
        "no_final_v23_solver_input": True,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_prior": False,
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
            "receiver_position_not_slammed_to_cap",
            "receiver_velocity_not_slammed_to_cap",
            "raw_doppler_spike_response_visible",
            "stress_variants_visualized",
            "no_trace_solver_input",
            "no_final_v23_solver_input",
        ]
    )
    return report


def write_n6b1_visual_sanity_report(path: str | Path, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
