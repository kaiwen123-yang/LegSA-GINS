"""N8E decision rules.

中文说明：决策规则只给工程阶段结论，不生成论文性能 claim。
"""

from __future__ import annotations

from typing import Any


def make_n8e_decision(
    *,
    matrix_report: dict[str, Any],
    caveat_report: dict[str, Any],
    claim_boundary_report: dict[str, Any],
    figure_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forbidden_claim_found = int(claim_boundary_report.get("forbidden_claim_count", 0) or 0) > 0
    matrix_complete = bool(matrix_report.get("matrix_complete"))
    fgo_boundary_ok = (
        bool(matrix_report.get("no_fgo_feedback"))
        and bool(matrix_report.get("no_fgo_output_substitution"))
        and bool(matrix_report.get("no_trace_finalv23_solver_input_or_tuning"))
        and not matrix_report.get("paper_performance_claim")
        and bool(caveat_report.get("all_required_caveats_present"))
        and not caveat_report.get("fgo_output_feedback_to_ekf")
        and not caveat_report.get("fgo_output_substitution")
    )
    if forbidden_claim_found:
        status = "claim_boundary_failed"
        next_stage = "N8E2_claim_cleanup"
    elif not matrix_complete:
        status = "ablation_matrix_incomplete"
        next_stage = "N8E2_ablation_recovery"
    elif not fgo_boundary_ok:
        status = "fgo_boundary_failed"
        next_stage = "N8E2_boundary_fix"
    else:
        status = "formal_engineering_ablation_ready_with_caveats"
        next_stage = "N9_paper_experiment_packaging_or_N8F_additional_data_review"

    figures = figure_manifest or {}
    return {
        "stage": "N8E_formal_engineering_ablation_with_caveat",
        "status": status,
        "recommended_next_stage": next_stage,
        "secondary_recommendation": "N8F_candidate_factor_review"
        if caveat_report.get("candidate_factors_need_deeper_review")
        else None,
        "matrix_complete": matrix_complete,
        "claim_boundary_decision": claim_boundary_report.get("decision"),
        "forbidden_claim_count": claim_boundary_report.get("forbidden_claim_count", 0),
        "required_caveats_present": caveat_report.get("all_required_caveats_present", False),
        "raw_doppler_fgo_active_but_low_marginal_value": matrix_report.get(
            "raw_doppler_fgo_active_but_low_marginal_value"
        ),
        "raw_doppler_low_marginal_value_is_not_failure": True,
        "candidate_factors_diagnostic_only": True,
        "figure_count_total": figures.get("figure_count_total", 0),
        "required_figures_nonempty": figures.get("required_figures_nonempty", False),
        "paper_performance_claim": False,
        "no_paper_performance_claim": True,
        "no_outperform_final_v23_claim": True,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "smoothness_factor_deleted_for_metric": False,
        "no_smoothness_final_shortcut": True,
    }
