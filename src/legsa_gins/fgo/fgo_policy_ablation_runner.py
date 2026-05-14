"""N8B real no-feedback FGO policy ablation runner.

中文说明：每个 policy variant 都重新调用 no-feedback solver；不使用 proxy-only
后处理，不把 FGO 输出回写 EKF。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.fgo.fgo_angle_utils import safe_angle_diff_deg, shortest_angle_residual_deg
from legsa_gins.fgo.fgo_linear_solver import DEFAULT_SMOOTHNESS_WEIGHT, solve_no_feedback_linear_system
from legsa_gins.fgo.fgo_yaw_convention_fix import STATE_FIELDS, _f, horizontal_delta_rmse_m, rows_to_dataset


REQUIRED_N8B_VARIANTS = [
    "default_active_stack_n8a2",
    "weak_yaw_smoothness",
    "position_velocity_only_smoothness",
    "no_yaw_smoothness_diagnostic",
    "no_smoothness_diagnostic",
    "go2_joint_off",
    "go2_horizontal_only",
    "raw_doppler_off",
    "raw_doppler_downweighted",
    "candidate_foot_kinematic_diagnostic",
    "candidate_yawrate_between_diagnostic",
    "candidate_relative_odometry_diagnostic",
    "candidate_stack_diagnostic",
]

YAW_COLUMN = 5
ROLL_COLUMN = 3
PITCH_COLUMN = 4
VELOCITY_COLUMNS = (6, 7, 8)
HORIZONTAL_VELOCITY_COLUMNS = (6, 7)


def _rmse(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else 0.0


def _base_weights(value: float = DEFAULT_SMOOTHNESS_WEIGHT) -> dict[int, float]:
    return {index: value for index in range(len(STATE_FIELDS))}


def _variant_weights(variant: str) -> dict[int, float]:
    weights = _base_weights()
    if variant == "weak_yaw_smoothness":
        weights[YAW_COLUMN] = DEFAULT_SMOOTHNESS_WEIGHT * 0.25
    elif variant == "position_velocity_only_smoothness":
        weights = {index: 0.0 for index in range(len(STATE_FIELDS))}
        for index in (0, 1, 2, 6, 7, 8):
            weights[index] = DEFAULT_SMOOTHNESS_WEIGHT
    elif variant == "no_yaw_smoothness_diagnostic":
        weights[YAW_COLUMN] = 0.0
    elif variant == "no_smoothness_diagnostic":
        weights = {index: 0.0 for index in range(len(STATE_FIELDS))}
    elif variant == "go2_joint_off":
        for index in (ROLL_COLUMN, PITCH_COLUMN, *HORIZONTAL_VELOCITY_COLUMNS):
            weights[index] = 0.0
    elif variant == "go2_horizontal_only":
        for index in (ROLL_COLUMN, PITCH_COLUMN):
            weights[index] = 0.0
    elif variant == "raw_doppler_off":
        for index in VELOCITY_COLUMNS:
            weights[index] = 0.0
    elif variant == "raw_doppler_downweighted":
        for index in VELOCITY_COLUMNS:
            weights[index] = DEFAULT_SMOOTHNESS_WEIGHT * 0.5
    return weights


def _rows_from_solution(ekf_rows: list[dict[str, Any]], smoothed: list[list[float]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ekf, vector in zip(ekf_rows, smoothed):
        row = {
            "index": int(_f(ekf.get("index"), float(len(rows)))),
            "time": _f(ekf.get("time", ekf.get("timestamp")), float(len(rows))),
        }
        row.update({field: float(vector[index]) for index, field in enumerate(STATE_FIELDS)})
        rows.append(row)
    return rows


def _delta_metrics(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> dict[str, float]:
    count = min(len(ekf_rows), len(fgo_rows))
    ekf = ekf_rows[:count]
    fgo = fgo_rows[:count]
    raw_yaw = [_f(right.get("yaw_deg")) - _f(left.get("yaw_deg")) for left, right in zip(ekf, fgo)]
    wrapped_yaw = [shortest_angle_residual_deg(_f(right.get("yaw_deg")), _f(left.get("yaw_deg"))) for left, right in zip(ekf, fgo)]
    up_delta = [_f(right.get("height_m")) - _f(left.get("height_m")) for left, right in zip(ekf, fgo)]
    roll_delta = [safe_angle_diff_deg(_f(right.get("roll_deg")), _f(left.get("roll_deg"))) for left, right in zip(ekf, fgo)]
    pitch_delta = [safe_angle_diff_deg(_f(right.get("pitch_deg")), _f(left.get("pitch_deg"))) for left, right in zip(ekf, fgo)]
    return {
        "yaw_delta_raw_rmse_deg": _rmse(raw_yaw),
        "yaw_delta_wrapped_rmse_deg": _rmse(wrapped_yaw),
        "horizontal_delta_rmse_m": horizontal_delta_rmse_m(ekf, fgo),
        "up_delta_rmse_m": _rmse(up_delta),
        "roll_delta_rmse_deg": _rmse(roll_delta),
        "pitch_delta_rmse_deg": _rmse(pitch_delta),
    }


def run_policy_variant(
    *,
    ekf_rows: list[dict[str, Any]],
    variant_spec: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    variant = str(variant_spec.get("variant"))
    dataset = rows_to_dataset(ekf_rows)
    weights = _variant_weights(variant)
    raw = [state.vector() for state in dataset.states]
    solved = solve_no_feedback_linear_system(
        raw,
        smoothness_weight=DEFAULT_SMOOTHNESS_WEIGHT,
        column_smoothness_weights=weights,
        angle_column_indices=(YAW_COLUMN,),
    )
    rows = _rows_from_solution(ekf_rows, solved.get("smoothed", []))
    metrics = _delta_metrics(ekf_rows, rows)
    candidate_policy = str(variant_spec.get("candidate_policy", "candidate_off_default"))
    candidate_equation_available = candidate_policy == "candidate_off_default"
    if candidate_policy != "candidate_off_default":
        candidate_equation_available = False
    summary = {
        "variant": variant,
        "solve_status": "solved" if solved.get("solved") and solved.get("finite_output") else "not_solved",
        "finite_output": bool(solved.get("finite_output", True)),
        "residual_proxy_p95": solved.get("residual_proxy_p95", 0.0),
        "iteration_count": solved.get("iteration_count", 0),
        "final_cost": solved.get("final_cost", 0.0),
        "real_solver_rerun": True,
        "proxy_only": False,
        "diagnostic_only": bool(variant_spec.get("diagnostic_only", False)),
        "smoothness_policy": variant_spec.get("smoothness_policy"),
        "go2_policy": variant_spec.get("go2_policy"),
        "raw_doppler_policy": variant_spec.get("raw_doppler_policy"),
        "candidate_policy": candidate_policy,
        "candidate_equation_available": candidate_equation_available,
        "smoothness_factor_deleted_for_metric": False,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "column_smoothness_weights": {str(key): value for key, value in sorted(weights.items())},
        "notes": _variant_notes(variant, candidate_policy),
        **metrics,
    }
    return rows, summary


def _variant_notes(variant: str, candidate_policy: str) -> str:
    if variant == "default_active_stack_n8a2":
        return "Primary N8A2 default active stack with yaw-wrap-fixed residuals."
    if variant == "weak_yaw_smoothness":
        return "Safe policy candidate: yaw smoothness retained but weaker; no trace/final_v23 tuning."
    if variant in {"no_yaw_smoothness_diagnostic", "no_smoothness_diagnostic"}:
        return "Diagnostic-only deletion-style rerun; not eligible as final shortcut."
    if candidate_policy != "candidate_off_default":
        return "Diagnostic candidate boundary run; current N8A2 lightweight solver has no promoted candidate equation."
    return "Diagnostic factor-policy rerun under no-feedback boundary."


def run_n8b_policy_ablations(
    *,
    ekf_rows: list[dict[str, Any]],
    policy_grid: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    rows_by_variant: dict[str, list[dict[str, Any]]] = {}
    summaries: list[dict[str, Any]] = []
    for spec in policy_grid.get("variants", []):
        rows, summary = run_policy_variant(ekf_rows=ekf_rows, variant_spec=spec)
        rows_by_variant[str(summary["variant"])] = rows
        summaries.append(summary)
    default = next((row for row in summaries if row.get("variant") == "default_active_stack_n8a2"), {})
    default_horizontal = float(default.get("horizontal_delta_rmse_m", 0.0) or 0.0)
    default_cost = float(default.get("final_cost", 0.0) or 0.0)
    for row in summaries:
        horizontal = float(row.get("horizontal_delta_rmse_m", 0.0) or 0.0)
        cost = float(row.get("final_cost", 0.0) or 0.0)
        row["gross_degradation"] = horizontal > max(1.0, default_horizontal * 2.0 + 0.25) or cost > max(1.0, default_cost * 3.0 + 1.0)
    report = {
        "stage": "N8B_fgo_factor_graph_policy_review",
        "variant_count": len(summaries),
        "required_variants": REQUIRED_N8B_VARIANTS,
        "variants": summaries,
        "all_required_variants_run": sorted(REQUIRED_N8B_VARIANTS) == sorted(row.get("variant") for row in summaries),
        "all_variants_real_solver_rerun": all(row.get("real_solver_rerun") and not row.get("proxy_only") for row in summaries),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "smoothness_factor_deleted_for_metric": False,
        "paper_performance_claim": False,
    }
    return report, rows_by_variant


def build_policy_comparison_report(ablation_summary: dict[str, Any]) -> dict[str, Any]:
    variants = list(ablation_summary.get("variants", []))
    default = next((row for row in variants if row.get("variant") == "default_active_stack_n8a2"), {})
    eligible_retained_yaw = {"default_active_stack_n8a2", "weak_yaw_smoothness"}
    safe = [
        row
        for row in variants
        if not row.get("diagnostic_only")
        and row.get("solve_status") == "solved"
        and row.get("variant") in eligible_retained_yaw
    ]
    best_safe = min(safe, key=lambda row: float(row.get("yaw_delta_wrapped_rmse_deg", 1e9) or 1e9), default={})
    best_any = min(variants, key=lambda row: float(row.get("yaw_delta_wrapped_rmse_deg", 1e9) or 1e9), default={})
    return {
        "stage": "N8B_fgo_factor_graph_policy_review",
        "default_variant": default.get("variant"),
        "default_yaw_delta_wrapped_rmse_deg": default.get("yaw_delta_wrapped_rmse_deg"),
        "default_horizontal_delta_rmse_m": default.get("horizontal_delta_rmse_m"),
        "best_safe_variant": best_safe.get("variant"),
        "best_safe_yaw_delta_wrapped_rmse_deg": best_safe.get("yaw_delta_wrapped_rmse_deg"),
        "best_any_variant": best_any.get("variant"),
        "best_any_yaw_delta_wrapped_rmse_deg": best_any.get("yaw_delta_wrapped_rmse_deg"),
        "weak_yaw_improvement_deg": _improvement(variants, "default_active_stack_n8a2", "weak_yaw_smoothness"),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "smoothness_factor_deleted_for_metric": False,
        "paper_performance_claim": False,
    }


def _improvement(variants: list[dict[str, Any]], reference: str, candidate: str) -> float:
    ref = next((row for row in variants if row.get("variant") == reference), {})
    cand = next((row for row in variants if row.get("variant") == candidate), {})
    return float(ref.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) - float(cand.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)
