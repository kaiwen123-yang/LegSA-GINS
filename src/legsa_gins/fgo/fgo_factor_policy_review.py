"""N8A1 factor-policy and residual contribution review.

中文说明：本模块审查默认 factor 栈、诊断候选泄漏和残差贡献代理。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry
from legsa_gins.fgo.fgo_yaw_convention_audit import as_float, percentile, rmse, wrap_delta_deg, yaw_delta_deg, yaw_series


REQUIRED_ACTIVE_FACTORS = {
    "ReceiverPositionFactor",
    "ReceiverVelocityFactor",
    "DualYawFactor",
    "RawDopplerVelocityFactor",
    "Go2ProprioceptiveJointFactor",
    "SmoothnessFactor",
}

N8A1_RECOMMENDED_ABLATIONS = [
    "default_active_stack",
    "no_smoothness",
    "weak_smoothness",
    "no_dual_yaw",
    "dual_yaw_stronger_diagnostic",
    "no_go2_joint",
    "no_raw_doppler",
    "no_go2_horizontal_component",
    "no_go2_rollpitch_component",
    "active_stack_no_diagnostic_candidates",
    "diagnostic_candidate_stack_if_available",
]


def _stats(values: list[float]) -> dict[str, float]:
    abs_values = [abs(value) for value in values if math.isfinite(value)]
    return {
        "p50": percentile(abs_values, 50),
        "p95": percentile(abs_values, 95),
        "max": max(abs_values) if abs_values else 0.0,
        "rmse": rmse(abs_values),
    }


def _position_delta_m(ekf: dict[str, Any], fgo: dict[str, Any]) -> float:
    lat0 = math.radians(as_float(ekf.get("lat_deg")))
    dlat = (as_float(fgo.get("lat_deg")) - as_float(ekf.get("lat_deg"))) * 111_320.0
    dlon = (as_float(fgo.get("lon_deg")) - as_float(ekf.get("lon_deg"))) * 111_320.0 * math.cos(lat0)
    dh = as_float(fgo.get("height_m")) - as_float(ekf.get("height_m"))
    return math.sqrt(dlat * dlat + dlon * dlon + dh * dh)


def _norm_delta(ekf: dict[str, Any], fgo: dict[str, Any], columns: list[str]) -> float:
    total = 0.0
    for column in columns:
        delta = as_float(fgo.get(column)) - as_float(ekf.get(column))
        total += delta * delta
    return math.sqrt(total)


def review_factor_policy(
    *,
    ekf_rows: list[dict[str, Any]],
    fgo_rows: list[dict[str, Any]],
    registry_report: dict[str, Any] | None = None,
    smoother_report: dict[str, Any] | None = None,
    yaw_convention_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry_report or build_default_factor_registry()
    smoother = smoother_report or {}
    convention = yaw_convention_report or {}
    active = set(registry.get("active_default_factors", []))
    diagnostic = set(registry.get("diagnostic_candidate_factors", []))
    factors = registry.get("factors", [])
    default_active_stack_valid = REQUIRED_ACTIVE_FACTORS.issubset(active)
    diagnostic_candidates_not_default = all(
        not factor.get("active_default", False)
        for factor in factors
        if factor.get("factor_name") in diagnostic or factor.get("diagnostic_only")
    )
    candidate_factor_leak_suspect = not diagnostic_candidates_not_default
    count = min(len(ekf_rows), len(fgo_rows))
    pairs = list(zip(ekf_rows[:count], fgo_rows[:count]))
    ekf_yaw = yaw_series(ekf_rows)[:count]
    fgo_yaw = yaw_series(fgo_rows)[:count]
    yaw_residual = [yaw_delta_deg(fgo, ekf) for ekf, fgo in zip(ekf_yaw, fgo_yaw)]
    smoothness_yaw_residual = [wrap_delta_deg(right - left) for left, right in zip(fgo_yaw, fgo_yaw[1:])]
    contribution_summary = [
        {"factor_type": "ReceiverPositionFactor", "residual_proxy_unit": "m", **_stats([_position_delta_m(ekf, fgo) for ekf, fgo in pairs])},
        {"factor_type": "ReceiverVelocityFactor", "residual_proxy_unit": "mps", **_stats([_norm_delta(ekf, fgo, ["vn_mps", "ve_mps", "vd_mps"]) for ekf, fgo in pairs])},
        {"factor_type": "DualYawFactor", "residual_proxy_unit": "deg", **_stats(yaw_residual)},
        {"factor_type": "Go2ProprioceptiveJointFactor", "residual_proxy_unit": "state_delta", **_stats([_norm_delta(ekf, fgo, ["roll_deg", "pitch_deg", "vn_mps", "ve_mps"]) for ekf, fgo in pairs])},
        {"factor_type": "SmoothnessFactor", "residual_proxy_unit": "deg_neighbor_yaw", **_stats(smoothness_yaw_residual)},
    ]
    for name in sorted(diagnostic):
        contribution_summary.append(
            {
                "factor_type": name,
                "residual_proxy_unit": "not_active_default",
                "p50": 0.0,
                "p95": 0.0,
                "max": 0.0,
                "rmse": 0.0,
                "diagnostic_only": True,
            }
        )
    yaw_p95 = next((row["p95"] for row in contribution_summary if row["factor_type"] == "DualYawFactor"), 0.0)
    smoothness_yaw_p95 = next((row["p95"] for row in contribution_summary if row["factor_type"] == "SmoothnessFactor"), 0.0)
    smoothness_weight_suspect = bool(convention.get("blocker_status") == "yaw_wrap_residual_blocker" or smoothness_yaw_p95 > 30.0)
    yaw_factor_weight_suspect = bool(yaw_p95 > 15.0 and "DualYawFactor" in active)
    return {
        "stage": "N8A1_fgo_yaw_delta_policy_review",
        "source_role_alias": "N8A_REPORT_OUTPUT_DIR",
        "default_active_stack_valid": default_active_stack_valid,
        "active_default_factors": sorted(active),
        "diagnostic_candidate_factors": sorted(diagnostic),
        "diagnostic_candidates_not_default": diagnostic_candidates_not_default,
        "smoothness_weight_suspect": smoothness_weight_suspect,
        "yaw_factor_weight_suspect": yaw_factor_weight_suspect,
        "candidate_factor_leak_suspect": candidate_factor_leak_suspect,
        "smoothness_weight_reported": smoother.get("smoothness_weight"),
        "dual_yaw_covariance_policy": next((factor.get("covariance_policy") for factor in factors if factor.get("factor_name") == "DualYawFactor"), ""),
        "smoothness_covariance_policy": next((factor.get("covariance_policy") for factor in factors if factor.get("factor_name") == "SmoothnessFactor"), ""),
        "yaw_rate_candidate_enabled_default": "Go2YawRateBetweenFactor" in active,
        "relative_odometry_candidate_enabled_default": "Go2RelativeOdometryBetweenFactor" in active,
        "go2_candidate_factors_diagnostic_only": diagnostic_candidates_not_default,
        "per_factor_contribution_summary": contribution_summary,
        "recommended_ablation": N8A1_RECOMMENDED_ABLATIONS,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "audit_only": True,
        "paper_performance_claim": False,
    }
