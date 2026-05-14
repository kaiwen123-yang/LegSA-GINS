"""N8C2 diagnostic candidate factor contribution review.

中文说明：候选因子保持 diagnostic-only，不在本阶段正式激活。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_factor_activation_audit import write_json_report
from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry


CANDIDATE_LABELS = {
    "Go2FootKinematicVelocityFactor": "foot kinematic velocity",
    "Go2YawRateBetweenFactor": "yaw-rate between",
    "Go2RelativeOdometryBetweenFactor": "relative odometry",
    "ContactProbabilityWeightingFactor": "contact probability weighting",
}


def build_candidate_factor_real_contribution_review(
    *,
    candidate_review: dict[str, Any],
    ablation_summary: dict[str, Any],
    registry_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry_report or build_default_factor_registry()
    diagnostic = set(registry.get("diagnostic_candidate_factors", []))
    candidate_rows = {row.get("factor_type"): row for row in candidate_review.get("candidate_factor_reviews", [])}
    variants = {row.get("variant"): row for row in ablation_summary.get("variants", [])}
    out_rows = []
    for factor, label in CANDIDATE_LABELS.items():
        source = candidate_rows.get(factor, {})
        variant = source.get("diagnostic_variant") or source.get("variant") or ""
        variant_summary = variants.get(variant, {})
        active_diagnostic = bool(variant_summary and variant_summary.get("candidate_equation_available", False))
        if factor in diagnostic and not active_diagnostic:
            status = "inactive_diagnostic"
            explanation = "Candidate is registered for diagnostics but has no promoted equation in the N8C2 solver."
        elif active_diagnostic:
            status = "weak_but_active"
            explanation = "Diagnostic variant exists with rows; it is not promoted as a formal factor."
        else:
            status = "inactive_diagnostic"
            explanation = "Candidate remains outside the default active factor stack."
        out_rows.append(
            {
                "factor_type": factor,
                "label": label,
                "diagnostic_registered": factor in diagnostic,
                "active_diagnostic": active_diagnostic,
                "residual_rows": 0 if not active_diagnostic else variant_summary.get("residual_proxy_p95", 0.0),
                "toggle_variant": variant,
                "formal_activation": False,
                "status": status,
                "explanation": explanation,
            }
        )
    return {
        "stage": "N8C2_fgo_factor_activation_review",
        "candidate_factor_rows": out_rows,
        "inactive_diagnostic_factors": [row["factor_type"] for row in out_rows if row["status"] == "inactive_diagnostic"],
        "weak_but_active_factors": [row["factor_type"] for row in out_rows if row["status"] == "weak_but_active"],
        "formal_activation": False,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
