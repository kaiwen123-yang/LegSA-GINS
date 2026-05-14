"""N8F no-feedback FGO runner with active legged candidate factors.

所有 variant 都实际进入 no-feedback solver rerun；候选足式因子打开时会改变
residual vector / factor table / Jacobian nonzero 统计。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .fgo_factor_activation_audit import residual_stats
from .fgo_foot_kinematic_velocity_factor import (
    inject_foot_kinematic_velocity,
    residuals_for_foot_kinematic_velocity,
)
from .fgo_formal_ablation_matrix import _column_weights, _factor_row, _rows_from_vectors
from .fgo_legged_factor_dataset_builder import LeggedFactorDataset, rows_to_vectors
from .fgo_linear_solver import DEFAULT_SMOOTHNESS_WEIGHT, solve_no_feedback_linear_system
from .fgo_policy_ablation_runner import _delta_metrics
from .fgo_raw_doppler_solver_injection import _inject_raw_doppler_measurements, assemble_raw_doppler_residual_vector
from .fgo_relative_odometry_between_factor import inject_relative_odometry_between, residuals_for_relative_odometry_between
from .fgo_weight_policy_grid import build_n8d_variant_specs
from .fgo_yaw_convention_fix import STATE_FIELDS
from .fgo_yawrate_between_factor import inject_yawrate_between, residuals_for_yawrate_between


YAW_COLUMN = 5


@dataclass(frozen=True)
class N8FVariantSpec:
    variant: str
    foot_enabled: bool = False
    contact_weighting_enabled: bool = False
    yawrate_enabled: bool = False
    relative_odometry_enabled: bool = False
    raw_doppler_enabled: bool = True
    go2_joint_enabled: bool = True
    diagnostic_only: bool = False
    candidate_strength_scale: float = 1.0


def build_n8f_variant_specs() -> List[N8FVariantSpec]:
    return [
        N8FVariantSpec("n8d_best_balance_baseline"),
        N8FVariantSpec("contact_weighting_only", contact_weighting_enabled=True),
        N8FVariantSpec("foot_kinematic_velocity_factor", foot_enabled=True),
        N8FVariantSpec("yawrate_between_factor", yawrate_enabled=True),
        N8FVariantSpec("relative_odometry_between_factor", relative_odometry_enabled=True),
        N8FVariantSpec("footkin_plus_contact_weighting", foot_enabled=True, contact_weighting_enabled=True),
        N8FVariantSpec("yawrate_plus_relative_odometry", yawrate_enabled=True, relative_odometry_enabled=True),
        N8FVariantSpec("all_legged_candidate_stack", foot_enabled=True, contact_weighting_enabled=True, yawrate_enabled=True, relative_odometry_enabled=True),
        N8FVariantSpec(
            "all_legged_candidate_stack_conservative",
            foot_enabled=True,
            contact_weighting_enabled=True,
            yawrate_enabled=True,
            relative_odometry_enabled=True,
            candidate_strength_scale=0.55,
        ),
        N8FVariantSpec(
            "all_legged_candidate_stack_aggressive_diagnostic",
            foot_enabled=True,
            contact_weighting_enabled=True,
            yawrate_enabled=True,
            relative_odometry_enabled=True,
            diagnostic_only=True,
            candidate_strength_scale=1.8,
        ),
        N8FVariantSpec("no_go2_joint_diagnostic", diagnostic_only=True, go2_joint_enabled=False),
        N8FVariantSpec("no_raw_doppler_diagnostic", diagnostic_only=True, raw_doppler_enabled=False),
    ]


def _n8d_best_balance_spec(spec: N8FVariantSpec) -> Dict[str, Any]:
    n8d_specs = build_n8d_variant_specs()
    base = dict(n8d_specs.get("conservative_policy", {"variant": "conservative_policy"}))
    base["variant"] = spec.variant
    base["raw_doppler_enabled"] = spec.raw_doppler_enabled
    base["go2_joint_enabled"] = spec.go2_joint_enabled
    return base


def _sum_rows_by_type(residual_rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for row in residual_rows:
        key = str(row.get("factor_type", "unknown"))
        out[key] = out.get(key, 0) + 1
    return out


def _sum_jacobian_by_type(residual_rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for row in residual_rows:
        key = str(row.get("factor_type", "unknown"))
        out[key] = out.get(key, 0) + int(row.get("jacobian_nonzero", 0) or 0)
    return out


def _candidate_factor_table_rows(
    *,
    spec: N8FVariantSpec,
    foot_rows: int,
    foot_residuals: int,
    foot_jac: int,
    yaw_rows: int,
    yaw_residuals: int,
    yaw_jac: int,
    relative_rows: int,
    relative_residuals: int,
    relative_jac: int,
) -> List[Dict[str, Any]]:
    rows = [
        {
            "variant": spec.variant,
            "factor_type": "ContactAwareWeightingLayer",
            "factor_count": 0,
            "residual_rows": 0,
            "jacobian_nonzero": 0,
            "enabled": spec.contact_weighting_enabled,
            "diagnostic_only": False,
        },
        {
            "variant": spec.variant,
            "factor_type": "FootKinematicVelocityFactor",
            "factor_count": foot_rows,
            "residual_rows": foot_residuals,
            "jacobian_nonzero": foot_jac,
            "enabled": spec.foot_enabled,
            "diagnostic_only": spec.diagnostic_only,
        },
        {
            "variant": spec.variant,
            "factor_type": "YawRateBetweenFactor",
            "factor_count": yaw_rows,
            "residual_rows": yaw_residuals,
            "jacobian_nonzero": yaw_jac,
            "enabled": spec.yawrate_enabled,
            "diagnostic_only": spec.diagnostic_only,
        },
        {
            "variant": spec.variant,
            "factor_type": "RelativeOdometryBetweenFactor",
            "factor_count": relative_rows,
            "residual_rows": relative_residuals,
            "jacobian_nonzero": relative_jac,
            "enabled": spec.relative_odometry_enabled,
            "diagnostic_only": spec.diagnostic_only,
        },
    ]
    return rows


def _build_legacy_factor_rows(
    *,
    state_count: int,
    raw_assembly: Mapping[str, Any],
    spec: N8FVariantSpec,
    solved: Mapping[str, Any],
) -> Dict[str, int]:
    return {
        "SmoothnessFactor": max(0, state_count - 1),
        "ReceiverPositionFactor": state_count,
        "ReceiverVelocityFactor": state_count,
        "DualYawFactor": state_count,
        "RawDopplerVelocityFactor": int(raw_assembly.get("raw_factor_rows", 0) or 0) if spec.raw_doppler_enabled else 0,
        "Go2ProprioceptiveJointFactor": state_count if spec.go2_joint_enabled else 0,
    }


def run_n8f_legged_variant(dataset: LeggedFactorDataset, spec: N8FVariantSpec) -> tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    ekf_rows = dataset.ekf_rows
    raw_vectors = rows_to_vectors(ekf_rows)
    n8d_spec = _n8d_best_balance_spec(spec)
    solved = solve_no_feedback_linear_system(
        raw_vectors,
        smoothness_weight=DEFAULT_SMOOTHNESS_WEIGHT,
        column_smoothness_weights=_column_weights(n8d_spec),
        angle_column_indices=(YAW_COLUMN,),
    )
    base_vectors = solved.get("smoothed", raw_vectors)
    solution_vectors = _inject_raw_doppler_measurements(
        base_vectors,
        dataset.raw_factors,
        raw_weight_scale=1.0 if spec.raw_doppler_enabled else 0.0,
        receiver_velocity_enabled=True,
    )
    if spec.foot_enabled:
        solution_vectors = inject_foot_kinematic_velocity(
            solution_vectors,
            dataset.foot_factor_rows,
            strength=0.16 * spec.candidate_strength_scale,
        )
    if spec.yawrate_enabled:
        solution_vectors = inject_yawrate_between(
            solution_vectors,
            dataset.yawrate_factor_rows,
            strength=0.11 * spec.candidate_strength_scale,
        )
    if spec.relative_odometry_enabled:
        solution_vectors = inject_relative_odometry_between(
            solution_vectors,
            dataset.relative_factor_rows,
            strength=0.07 * spec.candidate_strength_scale,
        )

    rows = _rows_from_vectors(ekf_rows, solution_vectors)
    raw_assembly = assemble_raw_doppler_residual_vector(
        solution_vectors=solution_vectors,
        factors=dataset.raw_factors,
        raw_enabled=spec.raw_doppler_enabled,
        raw_weight_scale=1.0,
    )
    foot_residuals = residuals_for_foot_kinematic_velocity(solution_vectors, dataset.foot_factor_rows) if spec.foot_enabled else []
    yaw_residuals = residuals_for_yawrate_between(solution_vectors, dataset.yawrate_factor_rows) if spec.yawrate_enabled else []
    relative_residuals = residuals_for_relative_odometry_between(solution_vectors, dataset.relative_factor_rows) if spec.relative_odometry_enabled else []
    candidate_residual_rows = foot_residuals + yaw_residuals + relative_residuals
    candidate_stats = residual_stats([float(row["whitened_residual"]) for row in candidate_residual_rows])

    legacy_factor_rows = _build_legacy_factor_rows(state_count=len(rows), raw_assembly=raw_assembly, spec=spec, solved=solved)
    candidate_residual_by_type = _sum_rows_by_type(candidate_residual_rows)
    candidate_jacobian_by_type = _sum_jacobian_by_type(candidate_residual_rows)
    factor_rows_by_type = {
        **legacy_factor_rows,
        "ContactAwareWeightingLayer": 0,
        "FootKinematicVelocityFactor": len(dataset.foot_factor_rows) if spec.foot_enabled else 0,
        "YawRateBetweenFactor": len(dataset.yawrate_factor_rows) if spec.yawrate_enabled else 0,
        "RelativeOdometryBetweenFactor": len(dataset.relative_factor_rows) if spec.relative_odometry_enabled else 0,
    }
    solver_residual_rows_by_type = {
        "SmoothnessFactor": max(0, len(rows) - 1) * len(STATE_FIELDS),
        "ReceiverVelocityFactor": len(rows) * 3,
        "DualYawFactor": len(rows),
        "RawDopplerVelocityFactor": int(raw_assembly.get("residual_row_count", 0) or 0),
        **candidate_residual_by_type,
    }
    jacobian_nonzero_by_type = {
        "RawDopplerVelocityFactor": int(raw_assembly.get("jacobian_nonzero_count", 0) or 0),
        **candidate_jacobian_by_type,
    }
    candidate_residual_dim = sum(candidate_residual_by_type.values())
    base_residual_dim = int(solved.get("state_count", len(rows)) or len(rows)) * len(STATE_FIELDS)
    solver_residual_dim = base_residual_dim + int(raw_assembly.get("residual_row_count", 0) or 0) + candidate_residual_dim
    delta_metrics = _delta_metrics(ekf_rows, rows)
    horizontal_delta_proxy = float(delta_metrics.get("horizontal_delta_rmse_m", 0.0) or 0.0)
    yaw_delta_proxy = float(delta_metrics.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)
    gross_degradation = bool(
        horizontal_delta_proxy > 8.0
        or yaw_delta_proxy > 12.0
        or candidate_stats.get("p95", 0.0) > 25.0
    )
    summary = {
        "stage": "N8F",
        "variant": spec.variant,
        "solve_status": "solved" if solved.get("solved") and solved.get("finite_output") else "not_solved",
        "finite_output": bool(solved.get("finite_output", True)),
        "real_solver_rerun": True,
        "proxy_only": False,
        "diagnostic_only": spec.diagnostic_only,
        "contact_weighting_enabled": spec.contact_weighting_enabled,
        "foot_kinematic_velocity_enabled": spec.foot_enabled,
        "yawrate_between_enabled": spec.yawrate_enabled,
        "relative_odometry_between_enabled": spec.relative_odometry_enabled,
        "raw_doppler_enabled": spec.raw_doppler_enabled,
        "go2_joint_enabled": spec.go2_joint_enabled,
        "solver_residual_dim": solver_residual_dim,
        "candidate_solver_residual_dim": candidate_residual_dim,
        "factor_rows_by_type": factor_rows_by_type,
        "solver_residual_rows_by_type": solver_residual_rows_by_type,
        "jacobian_nonzero_by_type": jacobian_nonzero_by_type,
        "candidate_whitened_residual_p50": candidate_stats["p50"],
        "candidate_whitened_residual_p95": candidate_stats["p95"],
        "candidate_whitened_residual_max": candidate_stats["max"],
        "residual_proxy_p95": solved.get("residual_proxy_p95", 0.0),
        "horizontal_delta_p95_m": horizontal_delta_proxy,
        "yaw_delta_p95_deg": yaw_delta_proxy,
        "roll_delta_p95_deg": float(delta_metrics.get("roll_delta_rmse_deg", 0.0) or 0.0),
        "pitch_delta_p95_deg": float(delta_metrics.get("pitch_delta_rmse_deg", 0.0) or 0.0),
        "final_cost": float(solved.get("final_cost", 0.0) or 0.0)
        + float(raw_assembly.get("whitened_residual_stats", {}).get("sum_sq", 0.0) or 0.0)
        + float(candidate_stats.get("sum_sq", 0.0) or 0.0),
        "gross_degradation_flag": gross_degradation,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "go2_truth_claim": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_contact_truth_claim": False,
        "go2_yaw_truth_claim": False,
        "paper_performance_claim": False,
        **delta_metrics,
    }
    table_rows = _candidate_factor_table_rows(
        spec=spec,
        foot_rows=factor_rows_by_type["FootKinematicVelocityFactor"],
        foot_residuals=solver_residual_rows_by_type.get("FootKinematicVelocityFactor", 0),
        foot_jac=jacobian_nonzero_by_type.get("FootKinematicVelocityFactor", 0),
        yaw_rows=factor_rows_by_type["YawRateBetweenFactor"],
        yaw_residuals=solver_residual_rows_by_type.get("YawRateBetweenFactor", 0),
        yaw_jac=jacobian_nonzero_by_type.get("YawRateBetweenFactor", 0),
        relative_rows=factor_rows_by_type["RelativeOdometryBetweenFactor"],
        relative_residuals=solver_residual_rows_by_type.get("RelativeOdometryBetweenFactor", 0),
        relative_jac=jacobian_nonzero_by_type.get("RelativeOdometryBetweenFactor", 0),
    )
    return rows, summary, table_rows


def run_n8f_legged_variants(dataset: LeggedFactorDataset, specs: Sequence[N8FVariantSpec] | None = None) -> tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    specs = list(specs or build_n8f_variant_specs())
    variant_rows: Dict[str, List[Dict[str, Any]]] = {}
    summaries: List[Dict[str, Any]] = []
    factor_table: List[Dict[str, Any]] = []
    for spec in specs:
        rows, summary, table_rows = run_n8f_legged_variant(dataset, spec)
        variant_rows[spec.variant] = rows
        summaries.append(summary)
        factor_table.extend(table_rows)
    baseline = next((row for row in summaries if row["variant"] == "n8d_best_balance_baseline"), {})
    for summary in summaries:
        summary["solver_residual_dim_delta_vs_baseline"] = int(summary.get("solver_residual_dim", 0) or 0) - int(
            baseline.get("solver_residual_dim", 0) or 0
        )
        summary["candidate_factor_rows_total"] = sum(
            int(summary.get("factor_rows_by_type", {}).get(name, 0) or 0)
            for name in ["FootKinematicVelocityFactor", "YawRateBetweenFactor", "RelativeOdometryBetweenFactor"]
        )
    report = {
        "stage": "N8F",
        "variant_count": len(summaries),
        "variants": summaries,
        "all_real_solver_reruns": all(bool(row.get("real_solver_rerun")) for row in summaries),
        "all_no_feedback": all(bool(row.get("no_feedback")) for row in summaries),
        "all_no_substitution": all(not bool(row.get("output_substitution")) for row in summaries),
        "all_no_trace_finalv23_tuning": all(
            not bool(row.get("trace_weight_tuning"))
            and not bool(row.get("final_v23_weight_tuning"))
            and not bool(row.get("trace_solver_input"))
            and not bool(row.get("final_v23_output_solver_input"))
            for row in summaries
        ),
        "all_no_go2_truth_claim": all(not bool(row.get("go2_truth_claim")) for row in summaries),
        "paper_performance_claim": False,
    }
    return report, variant_rows, factor_table
