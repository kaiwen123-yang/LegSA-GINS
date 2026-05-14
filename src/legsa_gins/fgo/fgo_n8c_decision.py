"""N8C no-feedback FGO visual decision rules.

中文说明：N8C 决策只描述工程诊断结论，不创建 paper performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n8c_decision(
    *,
    plot_coverage: dict[str, Any],
    visual_sanity: dict[str, Any],
    factor_contribution: dict[str, Any],
    candidate_review: dict[str, Any],
) -> dict[str, Any]:
    candidate_useful = any(row.get("status") == "candidate_useful_for_N8C" for row in candidate_review.get("candidate_factor_reviews", []))
    suspicious = list(factor_contribution.get("suspicious_no_effect_factors", []))
    if not plot_coverage.get("all_mandatory_figures_present") or not plot_coverage.get("all_mandatory_figures_nonempty"):
        status = "visual_validation_failed"
        next_stage = "N8C2_visual_recovery"
    elif not visual_sanity.get("yaw_delta_reasonable_after_n8a2") or not visual_sanity.get("visual_sanity_passed"):
        status = "weak_yaw_policy_not_ready"
        next_stage = "N8B2_smoothness_policy_review"
    elif suspicious:
        status = "factor_contribution_needs_review"
        next_stage = "N8C2_factor_activation_review"
    elif candidate_useful:
        status = "candidate_factor_ready_for_deeper_review"
        next_stage = "N8D_candidate_factor_ablation"
    else:
        status = "no_feedback_fgo_visual_validation_passed"
        next_stage = "N8D_formal_ablation_matrix_or_N9_paper_claim_boundary_review"
    return {
        "stage": "N8C_no_feedback_fgo_visual_validation",
        "status": status,
        "recommended_next_stage": next_stage,
        "suspicious_no_effect_factors": suspicious,
        "influential_factors": factor_contribution.get("influential_factors", []),
        "candidate_factor_statuses": [row.get("status") for row in candidate_review.get("candidate_factor_reviews", [])],
        "paper_performance_claim": False,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
    }


def write_n8c_decision(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
