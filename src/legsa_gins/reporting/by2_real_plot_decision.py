"""N8K2 real plot fix decision logic."""

# 中文说明：N8K2 决策只评价真实绘图修复是否完成，不产生论文性能结论。

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


def build_real_plot_decision(coverage: dict[str, Any]) -> dict[str, Any]:
    if coverage.get("applicable_placeholder_count", 0) > 0:
        status = "real_plot_fix_failed_placeholders_remain"
        next_stage = "N8K3_placeholder_recovery"
    elif coverage.get("unresolved_missing_data_count", 0) > 0 or coverage.get("missing_real_plot_count", 0) > 0:
        status = "real_plot_fix_failed_missing_data"
        next_stage = "N8K3_data_recovery"
    elif coverage.get("duplicate_template_suspect_count", 0) > 0:
        status = "real_plot_fix_failed_duplicate_templates"
        next_stage = "N8K3_duplicate_plot_fix"
    elif coverage.get("semantic_filename_mismatch_count", 0) > 0:
        status = "real_plot_fix_failed_semantic_filename_mismatch"
        next_stage = "N8K4_semantic_filename_plot_fix"
    elif coverage.get("all_categories_complete") is not True:
        status = "real_plot_fix_failed_coverage_incomplete"
        next_stage = "N8K3_plot_coverage_recovery"
    else:
        status = "BY2_formal_ablation_real_plot_fix_complete"
        next_stage = "N8K_merge_review_then_N9A_BY2_full_plot_audit"
    return {
        "stage": "N8K2",
        "status": status,
        "recommended_next_stage": next_stage,
        "applicable_placeholder_count": coverage.get("applicable_placeholder_count", 0),
        "duplicate_template_suspect_count": coverage.get("duplicate_template_suspect_count", 0),
        "missing_real_plot_count": coverage.get("missing_real_plot_count", 0),
        "unresolved_missing_data_count": coverage.get("unresolved_missing_data_count", 0),
        "low_information_unresolved_count": coverage.get("low_information_unresolved_count", 0),
        "no_algorithm_changes": True,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_real_plot_decision(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
