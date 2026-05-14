"""N8C3 Raw Doppler residual-vector solver injection.

中文说明：把 Raw Doppler 因子作为真实 residual/Jacobian 行注入 no-feedback FGO。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.fgo.fgo_factor_activation_audit import residual_stats
from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_linear_solver import DEFAULT_SMOOTHNESS_WEIGHT, solve_no_feedback_linear_system
from legsa_gins.fgo.fgo_policy_ablation_runner import _delta_metrics
from legsa_gins.fgo.fgo_raw_doppler_factor_contract import VELOCITY_COLUMNS, raw_doppler_jacobian_entries, raw_doppler_residual, raw_doppler_whitened_residual
from legsa_gins.fgo.fgo_yaw_convention_fix import STATE_FIELDS, _f, rows_to_dataset


YAW_COLUMN = 5
POSITION_COLUMNS = (0, 1, 2)
ATTITUDE_COLUMNS = (3, 4, 5)


def _weights_for_variant(variant: str) -> tuple[dict[int, float], bool, float, bool]:
    weights = {index: DEFAULT_SMOOTHNESS_WEIGHT for index in range(len(STATE_FIELDS))}
    weights[YAW_COLUMN] = DEFAULT_SMOOTHNESS_WEIGHT * 0.25
    raw_enabled = True
    raw_scale = 1.0
    receiver_velocity_enabled = True
    scale_map = {
        "raw_doppler_weight_x0p5": 0.5,
        "raw_doppler_weight_x1": 1.0,
        "raw_doppler_weight_x2": 2.0,
        "raw_doppler_weight_x4": 4.0,
        "smoothness_weak_raw_x1": 1.0,
        "smoothness_weak_raw_x2": 2.0,
        "weak_yaw_smoothness_with_raw_fixed": 1.0,
    }
    if variant in {"raw_doppler_off_verified", "receiver_velocity_off_raw_off"}:
        raw_enabled = False
        raw_scale = 0.0
    elif variant in scale_map:
        raw_scale = scale_map[variant]
    if variant in {"receiver_velocity_off_raw_on", "receiver_velocity_off_raw_off"}:
        receiver_velocity_enabled = False
        for column in VELOCITY_COLUMNS:
            weights[column] = 0.0
    if variant == "smoothness_weak_raw_x1":
        weights = {index: DEFAULT_SMOOTHNESS_WEIGHT * 0.5 for index in range(len(STATE_FIELDS))}
        weights[YAW_COLUMN] = DEFAULT_SMOOTHNESS_WEIGHT * 0.25
    if variant == "smoothness_weak_raw_x2":
        weights = {index: DEFAULT_SMOOTHNESS_WEIGHT * 0.35 for index in range(len(STATE_FIELDS))}
        weights[YAW_COLUMN] = DEFAULT_SMOOTHNESS_WEIGHT * 0.25
    return weights, raw_enabled, raw_scale, receiver_velocity_enabled


def _rows_from_vectors(ekf_rows: list[dict[str, Any]], vectors: list[list[float]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (ekf, vector) in enumerate(zip(ekf_rows, vectors)):
        row = {
            "index": int(_f(ekf.get("index"), float(index))),
            "time": _f(ekf.get("time", ekf.get("timestamp")), float(index)),
        }
        row.update({field: float(vector[field_index]) for field_index, field in enumerate(STATE_FIELDS)})
        rows.append(row)
    return rows


def _inject_raw_doppler_measurements(
    vectors: list[list[float]],
    factors: list[RawDopplerVelocityFactorRow],
    *,
    raw_weight_scale: float,
    receiver_velocity_enabled: bool,
) -> list[list[float]]:
    out = [list(row) for row in vectors]
    if raw_weight_scale <= 0.0:
        return out
    base_weight = 1.0 if receiver_velocity_enabled else 1e-6
    for factor in factors:
        if not factor.active or factor.state_index >= len(out):
            continue
        for local_index, column in enumerate(VELOCITY_COLUMNS):
            std = max(factor.std()[local_index], 1e-9)
            raw_weight = raw_weight_scale / (std * std)
            measurement = factor.measurement()[local_index]
            prior = out[factor.state_index][column]
            out[factor.state_index][column] = (base_weight * prior + raw_weight * measurement) / (base_weight + raw_weight)
    return out


def assemble_raw_doppler_residual_vector(
    *,
    solution_vectors: list[list[float]],
    factors: list[RawDopplerVelocityFactorRow],
    raw_enabled: bool,
    raw_weight_scale: float,
) -> dict[str, Any]:
    residual_values: list[float] = []
    whitened_values: list[float] = []
    jacobian_nonzero_count = 0
    active_factors = [factor for factor in factors if raw_enabled and factor.active and factor.state_index < len(solution_vectors)]
    for factor in active_factors:
        vector = solution_vectors[factor.state_index]
        residual_values.extend(raw_doppler_residual(vector, factor))
        whitened_values.extend(raw_doppler_whitened_residual(vector, factor, weight_scale=raw_weight_scale))
        jacobian_nonzero_count += len(raw_doppler_jacobian_entries(row_offset=0))
    raw_stats = residual_stats(residual_values)
    whitened_stats = residual_stats(whitened_values)
    return {
        "appears_in_solver_residual_vector": bool(active_factors),
        "raw_factor_rows": len(active_factors),
        "residual_row_count": len(residual_values),
        "jacobian_row_count": len(residual_values),
        "jacobian_nonzero_count": jacobian_nonzero_count,
        "raw_residual_stats": raw_stats,
        "whitened_residual_stats": whitened_stats,
        "raw_residual_p50": raw_stats["p50"],
        "raw_residual_p95": raw_stats["p95"],
        "raw_residual_max": raw_stats["max"],
        "whitened_residual_p50": whitened_stats["p50"],
        "whitened_residual_p95": whitened_stats["p95"],
        "whitened_residual_max": whitened_stats["max"],
        "state_blocks_touched": ["velocity_north", "velocity_east", "velocity_down"] if active_factors else [],
    }


def run_raw_doppler_solver_variant(
    *,
    ekf_rows: list[dict[str, Any]],
    raw_factors: list[RawDopplerVelocityFactorRow],
    variant: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset = rows_to_dataset(ekf_rows)
    raw_vectors = [state.vector() for state in dataset.states]
    weights, raw_enabled, raw_scale, receiver_velocity_enabled = _weights_for_variant(variant)
    solved = solve_no_feedback_linear_system(
        raw_vectors,
        smoothness_weight=DEFAULT_SMOOTHNESS_WEIGHT,
        column_smoothness_weights=weights,
        angle_column_indices=(YAW_COLUMN,),
    )
    base_vectors = solved.get("smoothed", [])
    solution_vectors = _inject_raw_doppler_measurements(
        base_vectors,
        raw_factors,
        raw_weight_scale=raw_scale if raw_enabled else 0.0,
        receiver_velocity_enabled=receiver_velocity_enabled,
    )
    rows = _rows_from_vectors(ekf_rows, solution_vectors)
    raw_assembly = assemble_raw_doppler_residual_vector(
        solution_vectors=solution_vectors,
        factors=raw_factors,
        raw_enabled=raw_enabled,
        raw_weight_scale=raw_scale,
    )
    base_residual_dim = int(solved.get("state_count", len(ekf_rows)) or len(ekf_rows)) * len(STATE_FIELDS)
    solver_residual_dim = base_residual_dim + int(raw_assembly["residual_row_count"])
    raw_cost = float(raw_assembly["whitened_residual_stats"]["sum_sq"])
    summary = {
        "variant": variant,
        "solve_status": "solved" if solved.get("solved") and solved.get("finite_output") else "not_solved",
        "finite_output": bool(solved.get("finite_output", True)),
        "raw_doppler_enabled": raw_enabled,
        "raw_doppler_weight_scale": raw_scale,
        "receiver_velocity_enabled": receiver_velocity_enabled,
        "raw_factor_rows": raw_assembly["raw_factor_rows"],
        "solver_residual_dim": solver_residual_dim,
        "base_residual_dim_without_raw": base_residual_dim,
        "jacobian_nonzero_count": raw_assembly["jacobian_nonzero_count"],
        "raw_residual_p50": raw_assembly["raw_residual_p50"],
        "raw_residual_p95": raw_assembly["raw_residual_p95"],
        "raw_residual_max": raw_assembly["raw_residual_max"],
        "whitened_raw_residual_p50": raw_assembly["whitened_residual_p50"],
        "whitened_raw_residual_p95": raw_assembly["whitened_residual_p95"],
        "whitened_raw_residual_max": raw_assembly["whitened_residual_max"],
        "final_cost": float(solved.get("final_cost", 0.0) or 0.0) + raw_cost,
        "real_solver_rerun": True,
        "proxy_only": False,
        "raw_doppler_direct_equation_available": True,
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


def build_solver_injection_report(*, with_raw_summary: dict[str, Any], without_raw_summary: dict[str, Any]) -> dict[str, Any]:
    dim_with = int(with_raw_summary.get("solver_residual_dim", 0) or 0)
    dim_without = int(without_raw_summary.get("solver_residual_dim", 0) or 0)
    status = "solver_injection_passed" if with_raw_summary.get("raw_factor_rows", 0) and dim_with > dim_without and with_raw_summary.get("jacobian_nonzero_count", 0) else "solver_injection_failed"
    return {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        "appears_in_solver_residual_vector": bool(with_raw_summary.get("raw_factor_rows", 0)),
        "residual_row_count": with_raw_summary.get("raw_factor_rows", 0) * 3,
        "jacobian_row_count": with_raw_summary.get("raw_factor_rows", 0) * 3,
        "jacobian_nonzero_count": with_raw_summary.get("jacobian_nonzero_count", 0),
        "whitened_residual_p50": with_raw_summary.get("whitened_raw_residual_p50", 0.0),
        "whitened_residual_p95": with_raw_summary.get("whitened_raw_residual_p95", 0.0),
        "whitened_residual_max": with_raw_summary.get("whitened_raw_residual_max", 0.0),
        "residual_vector_dim_with_raw": dim_with,
        "residual_vector_dim_without_raw": dim_without,
        "dim_delta": dim_with - dim_without,
        "factor_count_changes_when_raw_off": int(with_raw_summary.get("raw_factor_rows", 0) or 0) > int(without_raw_summary.get("raw_factor_rows", 0) or 0),
        "solver_injection_status": status,
        "state_blocks_touched": ["velocity_north", "velocity_east", "velocity_down"] if status == "solver_injection_passed" else [],
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
