"""N8H feedback visual-validation decision.

中文说明：按 N8H gate/position/variant/figure 规则给出阶段决策。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import PRIMARY_FEEDBACK_VARIANT, write_json


def build_visual_decision_report(
    *,
    visual_manifest: dict[str, Any],
    position_audit: dict[str, Any],
    variant_review: dict[str, Any],
    gate_review: dict[str, Any],
    correction_review: dict[str, Any],
    semantic_guard: dict[str, Any],
    plot_coverage: dict[str, Any],
) -> dict[str, Any]:
    if not plot_coverage.get("all_required_figures_nonempty"):
        status = "visual_validation_failed"
        next_stage = "N8H2_visual_recovery"
    elif position_audit.get("status") == "position_disabled_violation":
        status = "position_disabled_boundary_failed"
        next_stage = "N8H2_position_feedback_boundary_fix"
    elif variant_review.get("reject_all_sanity_passed") is not True:
        status = "reject_all_sanity_failed"
        next_stage = "N8H2_feedback_variant_debug"
    elif gate_review.get("all_feedback_accepted") is True and gate_review.get("classification") == "gate_too_loose_suspect":
        status = "feedback_gate_policy_needs_review"
        next_stage = "N8H2_feedback_gate_policy_review"
    elif _primary_gross_degradation(variant_review):
        status = "feedback_visual_degradation"
        next_stage = "N8H2_feedback_covariance_review"
    elif semantic_guard.get("status") != "plot_semantics_passed":
        status = "visual_validation_failed"
        next_stage = "N8H2_visual_recovery"
    else:
        status = "fgo_feedback_visual_validation_passed"
        next_stage = "N8G_merge_tag_then_N8I_feedback_ablation_or_N9_packaging"
    return {
        "stage": "N8H",
        "status": status,
        "recommended_next_stage": next_stage,
        "required_figures_nonempty": bool(plot_coverage.get("all_required_figures_nonempty")),
        "primary_position_disabled_status": position_audit.get("status"),
        "reject_all_sanity_passed": variant_review.get("reject_all_sanity_passed") is True,
        "gate_classification": gate_review.get("classification"),
        "primary_feedback_visual_gross_degradation": _primary_gross_degradation(variant_review),
        "correction_review_top_epoch_count": len(correction_review.get("top_correction_epochs", [])),
        "plot_semantic_status": semantic_guard.get("status"),
        "paper_performance_claim": False,
        "fgo_feedback_output_substitution": False,
        "fgo_feedback_direct_nav_override": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_finalv23_tuning": True,
        "fgo_feedback_no_future_data": True,
    }


def _primary_gross_degradation(variant_review: dict[str, Any]) -> bool:
    for item in variant_review.get("variants", []):
        if item.get("variant_id") == PRIMARY_FEEDBACK_VARIANT:
            return bool(item.get("gross_degradation"))
    return False


def write_visual_decision_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
