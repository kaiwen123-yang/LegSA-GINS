"""N8B diagnostic candidate factor review.

中文说明：候选 factor 在 N8B 只做诊断审查，不正式激活。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CANDIDATE_VARIANTS = {
    "Go2FootKinematicVelocityFactor": "candidate_foot_kinematic_diagnostic",
    "Go2YawRateBetweenFactor": "candidate_yawrate_between_diagnostic",
    "Go2RelativeOdometryBetweenFactor": "candidate_relative_odometry_diagnostic",
    "ContactProbabilityWeightingFactor": "candidate_stack_diagnostic",
}


def review_candidate_factors(
    *,
    ablation_summary: dict[str, Any],
    n7c6_available: bool = False,
    n7c5_available: bool = False,
) -> dict[str, Any]:
    variants = {str(row.get("variant")): row for row in ablation_summary.get("variants", [])}
    default = variants.get("default_active_stack_n8a2", {})
    default_yaw = float(default.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)
    default_horizontal = float(default.get("horizontal_delta_rmse_m", 0.0) or 0.0)
    reviews = []
    for factor, variant in CANDIDATE_VARIANTS.items():
        row = variants.get(variant, {})
        yaw = float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)
        horizontal = float(row.get("horizontal_delta_rmse_m", 0.0) or 0.0)
        equation_available = bool(row.get("candidate_equation_available", False))
        if not equation_available:
            status = "candidate_needs_data_review" if (n7c6_available or n7c5_available) else "candidate_not_ready"
        elif bool(row.get("gross_degradation", False)) or yaw > default_yaw * 1.25 + 0.25 or horizontal > default_horizontal * 1.25 + 0.25:
            status = "candidate_degrades"
        elif yaw < default_yaw and not bool(row.get("gross_degradation", False)):
            status = "candidate_useful_for_N8C"
        else:
            status = "candidate_not_ready"
        reviews.append(
            {
                "factor_type": factor,
                "variant": variant,
                "status": status,
                "diagnostic_only": True,
                "formal_activation": False,
                "candidate_equation_available": equation_available,
                "solve_status": row.get("solve_status"),
                "yaw_delta_wrapped_rmse_deg": row.get("yaw_delta_wrapped_rmse_deg"),
                "horizontal_delta_rmse_m": row.get("horizontal_delta_rmse_m"),
                "residual_proxy_p95": row.get("residual_proxy_p95"),
                "gross_degradation": row.get("gross_degradation"),
            }
        )
    return {
        "stage": "N8B_fgo_factor_graph_policy_review",
        "candidate_factor_reviews": reviews,
        "candidate_factors_tested": [row["factor_type"] for row in reviews],
        "candidate_factors_remain_diagnostic": True,
        "no_formal_activation": True,
        "n7c6_role_alias_available": bool(n7c6_available),
        "n7c5_role_alias_available": bool(n7c5_available),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }


def write_candidate_factor_review(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
