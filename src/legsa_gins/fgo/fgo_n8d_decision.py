"""N8D factor weight policy decision rules.

中文说明：N8D 只给工程权重审查结论，不做论文性能结论。
"""

from __future__ import annotations

from typing import Any


def make_n8d_decision(
    *,
    balance_report: dict[str, Any],
    smoothness_report: dict[str, Any],
    raw_receiver_report: dict[str, Any],
    go2_report: dict[str, Any],
    formal_matrix_report: dict[str, Any],
    figure_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    variants_ok = bool(formal_matrix_report.get("all_required_variants_run")) and bool(
        formal_matrix_report.get("all_variants_real_solver_rerun")
    )
    all_failed = not variants_ok
    if all_failed:
        status = "fgo_weight_policy_review_failed"
        next_stage = "N8D2_solver_stability_fix"
    elif smoothness_report.get("smoothness_still_dominant"):
        status = "process_factor_redesign_needed"
        next_stage = "N8D2_process_factor_redesign"
    elif raw_receiver_report.get("raw_doppler_remains_low_marginal_value"):
        status = "raw_doppler_active_but_low_fgo_marginal_value"
        next_stage = "N8E_formal_ablation_with_caveat"
    elif go2_report.get("go2_joint_stable_low_marginal_value"):
        status = "go2_joint_stable_low_marginal_value"
        next_stage = "N8E_formal_ablation_with_caveat"
    elif formal_matrix_report.get("gross_degradation_variants"):
        status = "default_stack_ready_candidates_not_ready"
        next_stage = "N8E_default_stack_validation"
    else:
        status = "balanced_weight_policy_ready"
        next_stage = "N8E_no_feedback_fgo_final_visual_validation"
    figures = figure_manifest or {}
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "status": status,
        "recommended_next_stage": next_stage,
        "best_solver_visible_balance_variant": formal_matrix_report.get("best_solver_visible_balance_variant"),
        "smoothness_dominance_detected": balance_report.get("smoothness_dominance_detected"),
        "raw_doppler_remains_low_marginal_value": raw_receiver_report.get("raw_doppler_remains_low_marginal_value"),
        "go2_joint_stable_low_marginal_value": go2_report.get("go2_joint_stable_low_marginal_value"),
        "figure_count_total": figures.get("figure_count_total", 0),
        "figures_nonempty": figures.get("required_figures_nonempty", False),
        "no_paper_performance_claim": True,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "smoothness_factor_deleted_for_metric": False,
        "no_smoothness_final_shortcut": True,
        "paper_performance_claim": False,
    }
