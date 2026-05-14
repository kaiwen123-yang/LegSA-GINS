"""N8C factor contribution review for no-feedback FGO.

中文说明：解释 factor on/off 指标变化，不把 candidate diagnostic factor 正式化。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry


FACTOR_VARIANT_MAP = {
    "RawDopplerVelocityFactor": "raw_doppler_off",
    "Go2ProprioceptiveJointFactor": "go2_joint_off",
    "Go2FootKinematicVelocityFactor": "candidate_foot_kinematic_diagnostic",
    "Go2YawRateBetweenFactor": "candidate_yawrate_between_diagnostic",
    "Go2RelativeOdometryBetweenFactor": "candidate_relative_odometry_diagnostic",
    "ContactProbabilityWeightingFactor": "candidate_stack_diagnostic",
}


def _variant(ablation_summary: dict[str, Any], name: str) -> dict[str, Any]:
    return next((row for row in ablation_summary.get("variants", []) if row.get("variant") == name), {})


def _delta(default: dict[str, Any], candidate: dict[str, Any], key: str) -> float:
    return float(candidate.get(key, 0.0) or 0.0) - float(default.get(key, 0.0) or 0.0)


def review_factor_contributions(
    *,
    ablation_summary: dict[str, Any],
    factor_weight_review: dict[str, Any],
    candidate_review: dict[str, Any],
) -> dict[str, Any]:
    registry = build_default_factor_registry()
    active = set(registry.get("active_default_factors", []))
    diagnostics = set(registry.get("diagnostic_candidate_factors", []))
    p95 = dict(factor_weight_review.get("per_factor_residual_p95", {}))
    default = _variant(ablation_summary, "default_active_stack_n8a2")
    weak = _variant(ablation_summary, "weak_yaw_smoothness")
    candidate_status = {row.get("factor_type"): row.get("status") for row in candidate_review.get("candidate_factor_reviews", [])}
    factors = [
        "ReceiverPositionFactor",
        "ReceiverVelocityFactor",
        "DualYawFactor",
        "RawDopplerVelocityFactor",
        "Go2ProprioceptiveJointFactor",
        "SmoothnessFactor",
        "Go2FootKinematicVelocityFactor",
        "Go2YawRateBetweenFactor",
        "Go2RelativeOdometryBetweenFactor",
        "ContactProbabilityWeightingFactor",
    ]
    rows = []
    for factor in factors:
        variant_name = FACTOR_VARIANT_MAP.get(factor, "")
        off = _variant(ablation_summary, variant_name) if variant_name else {}
        yaw_delta = _delta(default, off, "yaw_delta_wrapped_rmse_deg") if off else 0.0
        horiz_delta = _delta(default, off, "horizontal_delta_rmse_m") if off else 0.0
        residual = float(p95.get(factor, 0.0) or 0.0)
        active_default = factor in active
        diagnostic_only = factor in diagnostics
        has_residual_rows = factor in p95 and residual > 0.0
        if diagnostic_only:
            status = "inactive_diagnostic"
            explanation = "Candidate factor remains diagnostic-only and is not active in the default stack."
        elif factor == "SmoothnessFactor":
            weak_gain = float(default.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) - float(weak.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)
            status = "influential" if weak_gain > 0.5 else "weak_but_active"
            explanation = "Weak yaw smoothness materially changes yaw delta while retaining smoothness."
            yaw_delta = -weak_gain
        elif factor in {"ReceiverPositionFactor", "ReceiverVelocityFactor", "DualYawFactor"} and has_residual_rows:
            status = "weak_but_active" if residual < 5.0 else "influential"
            explanation = "Residual proxy is present; no safe on/off variant is defined for this core factor in N8C."
        elif factor == "Go2ProprioceptiveJointFactor" and has_residual_rows and abs(yaw_delta) < 0.05 and abs(horiz_delta) < 0.05:
            status = "consistent_no_large_delta"
            explanation = "Residual proxy exists, but go2_joint_off changes metrics only slightly; contribution is consistent with baseline rather than visibly dominant."
        elif active_default and not has_residual_rows:
            status = "suspicious_no_effect"
            explanation = "Factor is registered active but no direct residual proxy rows were found in the N8B factor-weight report."
        elif active_default:
            status = "consistent_no_large_delta"
            explanation = "On/off diagnostic delta is small under the no-feedback FGO proxy solver."
        else:
            status = "inactive_diagnostic"
            explanation = "Factor is not active in the default stack."
        rows.append(
            {
                "factor_type": factor,
                "active_in_default": active_default,
                "diagnostic_only": diagnostic_only,
                "residual_p95": residual,
                "on_off_variant": variant_name,
                "on_off_yaw_delta_rmse_change_deg": yaw_delta,
                "on_off_horizontal_delta_rmse_change_m": horiz_delta,
                "contribution_status": status,
                "candidate_review_status": candidate_status.get(factor, ""),
                "explanation": explanation,
            }
        )
    suspicious = [row["factor_type"] for row in rows if row["contribution_status"] == "suspicious_no_effect"]
    return {
        "stage": "N8C_no_feedback_fgo_visual_validation",
        "factor_contribution_rows": rows,
        "influential_factors": [row["factor_type"] for row in rows if row["contribution_status"] == "influential"],
        "weak_but_active_factors": [row["factor_type"] for row in rows if row["contribution_status"] == "weak_but_active"],
        "consistent_no_large_delta_factors": [row["factor_type"] for row in rows if row["contribution_status"] == "consistent_no_large_delta"],
        "inactive_diagnostic_factors": [row["factor_type"] for row in rows if row["contribution_status"] == "inactive_diagnostic"],
        "suspicious_no_effect_factors": suspicious,
        "review_complete": True,
        "candidate_factors_diagnostic_only": True,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
    }


def write_factor_contribution_review(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
