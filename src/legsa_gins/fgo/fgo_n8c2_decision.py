"""N8C2 decision rules for factor activation and residual whitening.

中文说明：N8C2 决策只给工程下一步，不做论文性能结论。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_factor_activation_audit import write_json_report


def make_n8c2_decision(
    *,
    activation_report: dict[str, Any],
    whitening_report: dict[str, Any],
    smoothness_report: dict[str, Any],
    raw_doppler_report: dict[str, Any],
    toggle_report: dict[str, Any],
    figure_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_class = raw_doppler_report.get("classification")
    toggle_status = toggle_report.get("status")
    smooth_class = whitening_report.get("smoothness_dominance_classification")
    if raw_class == "activation_missing":
        status = "raw_doppler_activation_missing"
        next_stage = "N8C3_raw_doppler_factor_fix"
    elif toggle_status == "toggle_integrity_failed":
        status = "raw_doppler_toggle_bug"
        next_stage = "N8C3_factor_toggle_fix"
    elif raw_class in {"dominated_by_receiver_velocity_smoothness", "weight_too_weak"}:
        status = "raw_doppler_active_but_dominated"
        next_stage = "N8D_factor_weight_policy_review"
    elif raw_class == "consistent_no_large_delta":
        status = "raw_doppler_active_consistent_no_large_delta"
        next_stage = "N8D_formal_ablation_matrix"
    elif smooth_class == "true_residual_dominance":
        status = "smoothness_process_model_needs_redesign"
        next_stage = "N8D_process_factor_redesign"
    elif smooth_class == "count_dominance":
        status = "factor_activation_review_passed_with_smoothness_count_caveat"
        next_stage = "N8D_formal_ablation_matrix"
    else:
        status = "factor_activation_review_passed"
        next_stage = "N8D_formal_ablation_matrix"
    figures = figure_manifest or {}
    return {
        "stage": "N8C2_fgo_factor_activation_review",
        "status": status,
        "recommended_next_stage": next_stage,
        "raw_doppler_classification": raw_class,
        "smoothness_dominance_classification": smooth_class,
        "smoothness_component_causing_spikes": smoothness_report.get("component_causing_spikes"),
        "toggle_integrity_status": toggle_status,
        "figure_count_total": figures.get("figure_count_total", 0),
        "figures_nonempty": figures.get("required_figures_nonempty", False),
        "activation_classification_counts": activation_report.get("classification_counts", {}),
        "no_paper_performance_claim": True,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
