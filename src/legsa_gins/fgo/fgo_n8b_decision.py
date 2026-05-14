"""N8B factor graph policy decision rules.

中文说明：N8B 决策只给后续阶段建议，不做 paper performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n8b_decision(
    *,
    ablation_summary: dict[str, Any],
    smoothness_review: dict[str, Any],
    factor_weight_review: dict[str, Any],
    candidate_review: dict[str, Any],
    figure_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    figures = figure_manifest or {}
    variants = list(ablation_summary.get("variants", []))
    all_failed = bool(variants) and all(row.get("solve_status") != "solved" or not row.get("finite_output") for row in variants)
    weak_ready = bool(smoothness_review.get("weak_yaw_smoothness_improves_without_degradation", False))
    no_yaw_best = bool(smoothness_review.get("no_yaw_smoothness_best_diagnostic", False))
    candidate_statuses = [row.get("status") for row in candidate_review.get("candidate_factor_reviews", [])]
    candidate_degrades = any(status == "candidate_degrades" for status in candidate_statuses)
    candidate_useful = any(status == "candidate_useful_for_N8C" for status in candidate_statuses)
    if all_failed:
        status = "fgo_policy_review_failed"
        next_stage = "N8B2_solver_stability_fix"
    elif weak_ready:
        status = "weak_yaw_smoothness_policy_ready"
        next_stage = "N8C_no_feedback_fgo_visual_validation"
    elif no_yaw_best:
        status = "yaw_smoothness_redesign_needed"
        next_stage = "N8B2_yaw_smoothness_redesign"
    elif candidate_degrades:
        status = "default_stack_ready_candidates_not_ready"
        next_stage = "N8C_default_stack_visual_validation"
    elif candidate_useful:
        status = "candidate_factor_ready_for_N8C_review"
        next_stage = "N8C_candidate_factor_visual_validation"
    else:
        status = "default_stack_ready_candidates_not_ready"
        next_stage = "N8C_default_stack_visual_validation"
    return {
        "stage": "N8B_fgo_factor_graph_policy_review",
        "status": status,
        "recommended_next_stage": next_stage,
        "recommended_smoothness_policy": smoothness_review.get("recommended_policy"),
        "secondary_recommendation": smoothness_review.get("secondary_recommendation", ""),
        "suspect_factors": factor_weight_review.get("suspect_factors", []),
        "candidate_statuses": candidate_statuses,
        "all_required_variants_run": ablation_summary.get("all_required_variants_run", False),
        "all_variants_real_solver_rerun": ablation_summary.get("all_variants_real_solver_rerun", False),
        "figures_generated": figures.get("required_figures_generated", False),
        "figures_nonempty": figures.get("required_figures_nonempty", False),
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "smoothness_factor_deleted_for_metric": False,
        "smoothness_deletion_final_shortcut": False,
        "paper_performance_claim": False,
    }


def write_n8b_decision(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
