"""N8K BY2 formal ablation plot-audit decision."""

# 中文说明：N8K 决策只判断正式消融和绘图审计是否完成。

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


def build_n8k_decision(matrix: dict[str, Any], coverage: dict[str, Any], semantic_guard: dict[str, Any], degradation_plan: dict[str, Any]) -> dict[str, Any]:
    if matrix.get("failed_count", 0) > 0 or matrix.get("completed_count") != matrix.get("variant_count"):
        status, next_stage = "formal_ablation_incomplete", "N8K2_ablation_recovery"
    elif coverage.get("all_required_categories_complete") is not True:
        status, next_stage = "ablation_plot_audit_incomplete", "N8K2_plot_recovery"
    elif semantic_guard.get("all_checks_passed") is not True:
        status, next_stage = "plot_or_claim_semantic_failed", "N8K2_semantic_fix"
    elif degradation_plan.get("degradation_matrix_run") is True:
        status, next_stage = "unexpected_degradation_run", "N8K2_scope_cleanup"
    else:
        status, next_stage = "BY2_formal_ablation_plot_audit_complete", "N9A_BY2_full_plot_audit"
    return {
        "stage": "N8K",
        "status": status,
        "recommended_next_stage": next_stage,
        "formal_ablation_variant_count": matrix.get("variant_count"),
        "completed_count": matrix.get("completed_count"),
        "failed_count": matrix.get("failed_count"),
        "total_figures_generated": coverage.get("total_png_figures_generated"),
        "missing_plot_count": coverage.get("missing_count"),
        "not_applicable_count": coverage.get("not_applicable_count"),
        "no_algorithm_changes": True,
        "feedback_policy_changed": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_n8k_decision(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
