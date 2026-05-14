"""N8F1 visual validation decision.

中文说明：N8F1 只决定 PR #44 是否具备后续 merge/tag 前的图像审查条件。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def build_n8f1_decision_report(
    *,
    figure_manifest: Mapping[str, Any],
    coverage_report: Mapping[str, Any],
    signal_report: Mapping[str, Any],
    semantic_report: Mapping[str, Any],
    sanity_report: Mapping[str, Any],
) -> dict[str, Any]:
    if not figure_manifest.get("required_figures_generated") or not figure_manifest.get("required_figures_nonempty"):
        status = "visual_validation_failed_missing_figures"
        next_stage = "N8F2_visual_recovery"
    elif not semantic_report.get("semantic_guard_passed"):
        status = "visual_validation_failed_semantics"
        next_stage = "N8F2_plot_semantic_fix"
    elif not signal_report.get("all_new_factors_have_real_signal"):
        status = "factor_signal_review_failed"
        next_stage = "N8F2_factor_signal_debug"
    elif signal_report.get("candidate_stack", {}).get("gross_degradation_flag"):
        status = "legged_candidate_stack_not_ready"
        next_stage = "N8F2_candidate_policy_review"
    elif coverage_report.get("visual_validation_passed") and sanity_report.get("visual_sanity_passed"):
        status = "legged_candidate_factor_visual_validation_passed"
        next_stage = "N8F_merge_tag_then_N8G_feedback_ekf_foundation"
    else:
        status = "visual_validation_failed_missing_figures"
        next_stage = "N8F2_visual_recovery"
    return {
        "stage": "N8F1",
        "status": status,
        "recommended_next_stage": next_stage,
        "figure_count": figure_manifest.get("figure_count_total", 0),
        "required_figures_generated": bool(figure_manifest.get("required_figures_generated")),
        "required_figures_nonempty": bool(figure_manifest.get("required_figures_nonempty")),
        "visual_validation_passed": status == "legged_candidate_factor_visual_validation_passed",
        "paper_performance_claim": False,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "finalv23_solver_input": False,
        "trace_weight_tuning": False,
        "finalv23_weight_tuning": False,
        "go2_truth_claim": False,
        "no_go2_truth_claim": True,
    }


def write_n8f1_decision_report(path: str | Path, report: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output

