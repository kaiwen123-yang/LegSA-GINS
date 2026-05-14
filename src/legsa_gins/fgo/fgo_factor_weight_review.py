"""N8B factor weight and residual-scale review.

中文说明：本模块只汇总 factor 残差和权重尺度，不用 trace/final_v23 调权。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_policy_review import review_factor_policy
from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry


DEFAULT_EFFECTIVE_WEIGHT_SCALE = {
    "ReceiverPositionFactor": "receiver_position_covariance",
    "ReceiverVelocityFactor": "receiver_velocity_covariance",
    "DualYawFactor": "dual_yaw_std",
    "RawDopplerVelocityFactor": "raw_doppler_covariance",
    "Go2ProprioceptiveJointFactor": "diag_go2_roll_pitch_horizontal_velocity_std",
    "SmoothnessFactor": "fixed_temporal_smoothness_weight_0.15",
    "Go2FootKinematicVelocityFactor": "diagnostic_candidate_covariance",
    "Go2YawRateBetweenFactor": "diagnostic_between_factor_covariance",
    "Go2RelativeOdometryBetweenFactor": "diagnostic_between_factor_covariance",
    "ContactProbabilityWeightingFactor": "weighting_only_not_hard_prior",
}


def review_factor_weights(
    *,
    ekf_rows: list[dict[str, Any]],
    default_fgo_rows: list[dict[str, Any]],
    ablation_summary: dict[str, Any],
) -> dict[str, Any]:
    registry = build_default_factor_registry()
    policy = review_factor_policy(ekf_rows=ekf_rows, fgo_rows=default_fgo_rows, registry_report=registry)
    per_factor = []
    suspect_factors = []
    for row in policy.get("per_factor_contribution_summary", []):
        factor = str(row.get("factor_type"))
        p95 = float(row.get("p95", 0.0) or 0.0)
        max_value = float(row.get("max", 0.0) or 0.0)
        over_constrained = factor == "SmoothnessFactor" and p95 > 5.0
        under_constrained = factor == "DualYawFactor" and p95 > 10.0
        stuck = max_value == 0.0 and not row.get("diagnostic_only", False)
        if over_constrained or under_constrained or stuck:
            suspect_factors.append(factor)
        per_factor.append(
            {
                "factor_type": factor,
                "p50": row.get("p50"),
                "p95": row.get("p95"),
                "max": row.get("max"),
                "rmse": row.get("rmse"),
                "effective_weight_scale": DEFAULT_EFFECTIVE_WEIGHT_SCALE.get(factor, "unknown"),
                "over_constrained_suspect": over_constrained,
                "under_constrained_suspect": under_constrained,
                "stuck_at_zero_or_cap_suspect": stuck,
                "diagnostic_only": bool(row.get("diagnostic_only", False)),
            }
        )
    weak = next((row for row in ablation_summary.get("variants", []) if row.get("variant") == "weak_yaw_smoothness"), {})
    default = next((row for row in ablation_summary.get("variants", []) if row.get("variant") == "default_active_stack_n8a2"), {})
    recommended = "weak_yaw_smoothness_diagnostic_policy" if float(default.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) > float(weak.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) else "keep_default_pending_more_evidence"
    return {
        "stage": "N8B_fgo_factor_graph_policy_review",
        "per_factor_residual_summary": per_factor,
        "per_factor_residual_p95": {row["factor_type"]: row["p95"] for row in per_factor},
        "suspect_factors": sorted(set(suspect_factors)),
        "smoothness_overconstrained_suspect": "SmoothnessFactor" in suspect_factors,
        "dual_yaw_underconstrained_suspect": "DualYawFactor" in suspect_factors,
        "recommended_diagnostic_weight_policy": recommended,
        "default_active_stack_valid": policy.get("default_active_stack_valid"),
        "candidate_factor_leak_suspect": policy.get("candidate_factor_leak_suspect"),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }


def write_factor_weight_review(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
