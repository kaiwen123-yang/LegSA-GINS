"""N8C2 diagnostic RawDopplerVelocityFactor weight sensitivity reruns.

中文说明：权重扫描只做诊断重跑，不按 trace/final_v23 选择最终权重。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.fgo.fgo_factor_activation_audit import build_factor_residual_series, residual_stats, write_json_report
from legsa_gins.fgo.fgo_linear_solver import DEFAULT_SMOOTHNESS_WEIGHT, solve_no_feedback_linear_system
from legsa_gins.fgo.fgo_policy_ablation_runner import _delta_metrics
from legsa_gins.fgo.fgo_yaw_convention_fix import STATE_FIELDS, _f, rows_to_dataset


RAW_DOPPLER_SENSITIVITY_VARIANTS = [
    "baseline_current_weak_yaw",
    "raw_doppler_off",
    "raw_doppler_weight_x0p25",
    "raw_doppler_weight_x0p5",
    "raw_doppler_weight_x1",
    "raw_doppler_weight_x2",
    "raw_doppler_weight_x4",
    "receiver_velocity_off_raw_on",
    "receiver_velocity_off_raw_off",
    "smoothness_weak_raw_x1",
    "smoothness_weak_raw_x2",
    "smoothness_component_split_raw_x1",
]

YAW_COLUMN = 5
VELOCITY_COLUMNS = (6, 7, 8)
POSITION_COLUMNS = (0, 1, 2)
ATTITUDE_COLUMNS = (3, 4, 5)


def _base_weights() -> dict[int, float]:
    weights = {index: DEFAULT_SMOOTHNESS_WEIGHT for index in range(len(STATE_FIELDS))}
    weights[YAW_COLUMN] = DEFAULT_SMOOTHNESS_WEIGHT * 0.25
    return weights


def _variant_weights(variant: str) -> tuple[dict[int, float], float]:
    weights = _base_weights()
    raw_scale = 1.0
    scale_map = {
        "raw_doppler_weight_x0p25": 0.25,
        "raw_doppler_weight_x0p5": 0.5,
        "raw_doppler_weight_x1": 1.0,
        "raw_doppler_weight_x2": 2.0,
        "raw_doppler_weight_x4": 4.0,
        "smoothness_weak_raw_x1": 1.0,
        "smoothness_weak_raw_x2": 2.0,
        "smoothness_component_split_raw_x1": 1.0,
    }
    if variant == "raw_doppler_off" or variant == "receiver_velocity_off_raw_off":
        raw_scale = 0.0
    elif variant in scale_map:
        raw_scale = scale_map[variant]
    if variant == "smoothness_weak_raw_x1":
        weights = {index: DEFAULT_SMOOTHNESS_WEIGHT * 0.5 for index in range(len(STATE_FIELDS))}
        weights[YAW_COLUMN] = DEFAULT_SMOOTHNESS_WEIGHT * 0.25
    if variant == "smoothness_weak_raw_x2":
        weights = {index: DEFAULT_SMOOTHNESS_WEIGHT * 0.5 for index in range(len(STATE_FIELDS))}
        weights[YAW_COLUMN] = DEFAULT_SMOOTHNESS_WEIGHT * 0.25
    if variant == "smoothness_component_split_raw_x1":
        weights = {index: DEFAULT_SMOOTHNESS_WEIGHT * 0.35 for index in range(len(STATE_FIELDS))}
        for index in POSITION_COLUMNS:
            weights[index] = DEFAULT_SMOOTHNESS_WEIGHT * 0.75
        for index in ATTITUDE_COLUMNS:
            weights[index] = DEFAULT_SMOOTHNESS_WEIGHT * 0.25
    for index in VELOCITY_COLUMNS:
        weights[index] = DEFAULT_SMOOTHNESS_WEIGHT * raw_scale
    if variant == "receiver_velocity_off_raw_on":
        for index in VELOCITY_COLUMNS:
            weights[index] = DEFAULT_SMOOTHNESS_WEIGHT
    return weights, raw_scale


def _rows_from_solution(ekf_rows: list[dict[str, Any]], smoothed: list[list[float]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (ekf, vector) in enumerate(zip(ekf_rows, smoothed)):
        row = {
            "index": int(_f(ekf.get("index"), float(index))),
            "time": _f(ekf.get("time", ekf.get("timestamp")), float(index)),
        }
        row.update({field: float(vector[field_index]) for field_index, field in enumerate(STATE_FIELDS)})
        rows.append(row)
    return rows


def _run_variant(ekf_rows: list[dict[str, Any]], variant: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset = rows_to_dataset(ekf_rows)
    raw = [state.vector() for state in dataset.states]
    weights, raw_scale = _variant_weights(variant)
    solved = solve_no_feedback_linear_system(
        raw,
        smoothness_weight=DEFAULT_SMOOTHNESS_WEIGHT,
        column_smoothness_weights=weights,
        angle_column_indices=(YAW_COLUMN,),
    )
    rows = _rows_from_solution(ekf_rows, solved.get("smoothed", []))
    _, residuals = build_factor_residual_series(factor_name="RawDopplerVelocityFactor", ekf_rows=ekf_rows, fgo_rows=rows)
    raw_stats = residual_stats(residuals)
    whitened_stats = residual_stats(residuals)
    summary = {
        "variant": variant,
        "solve_status": "solved" if solved.get("solved") and solved.get("finite_output") else "not_solved",
        "finite_output": bool(solved.get("finite_output", True)),
        "raw_doppler_weight_scale": raw_scale,
        "raw_factor_residual_p95_raw": raw_stats["p95"],
        "raw_factor_residual_p95_whitened": whitened_stats["p95"],
        "final_cost": solved.get("final_cost", 0.0),
        "real_solver_rerun": True,
        "proxy_only": False,
        "raw_doppler_direct_equation_available": False,
        "diagnostic_only": True,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        **_delta_metrics(ekf_rows, rows),
    }
    return rows, summary


def run_raw_doppler_weight_sensitivity(*, ekf_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    rows_by_variant: dict[str, list[dict[str, Any]]] = {}
    summaries = []
    for variant in RAW_DOPPLER_SENSITIVITY_VARIANTS:
        rows, summary = _run_variant(ekf_rows, variant)
        rows_by_variant[variant] = rows
        summaries.append(summary)
    baseline = next((row for row in summaries if row.get("variant") == "baseline_current_weak_yaw"), {})
    base_horizontal = float(baseline.get("horizontal_delta_rmse_m", 0.0) or 0.0)
    base_cost = float(baseline.get("final_cost", 0.0) or 0.0)
    for row in summaries:
        horizontal = float(row.get("horizontal_delta_rmse_m", 0.0) or 0.0)
        cost = float(row.get("final_cost", 0.0) or 0.0)
        row["gross_degradation"] = horizontal > max(1.0, base_horizontal * 2.0 + 0.25) or cost > max(1.0, base_cost * 3.0 + 1.0)
    report = {
        "stage": "N8C2_fgo_factor_activation_review",
        "variants": summaries,
        "variant_count": len(summaries),
        "required_variants": RAW_DOPPLER_SENSITIVITY_VARIANTS,
        "all_required_variants_run": sorted(RAW_DOPPLER_SENSITIVITY_VARIANTS) == sorted(row.get("variant") for row in summaries),
        "all_variants_real_solver_rerun": all(row.get("real_solver_rerun") and not row.get("proxy_only") for row in summaries),
        "weight_scan_diagnostic_only": True,
        "no_final_weight_selected_by_trace": True,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
    return report, rows_by_variant
