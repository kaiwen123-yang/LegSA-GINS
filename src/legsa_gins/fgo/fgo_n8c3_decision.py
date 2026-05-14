"""N8C3 Raw Doppler factor fix decision rules.

中文说明：N8C3 决策只判断 Raw Doppler solver 激活是否修复，不进入 N8D 执行。
"""

from __future__ import annotations

from typing import Any


def make_n8c3_decision(
    *,
    dataset_link_report: dict[str, Any],
    solver_injection_report: dict[str, Any],
    toggle_regression_report: dict[str, Any],
    variant_report: dict[str, Any],
    figure_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not dataset_link_report.get("source_found"):
        status = "raw_doppler_source_missing"
        next_stage = "N8C4_source_recovery"
    elif int(dataset_link_report.get("aligned_factor_count", 0) or 0) == 0:
        status = "raw_doppler_alignment_blocker"
        next_stage = "N8C4_time_alignment_fix"
    elif not solver_injection_report.get("appears_in_solver_residual_vector"):
        status = "raw_doppler_solver_injection_failed"
        next_stage = "N8C4_solver_injection_fix"
    elif int(solver_injection_report.get("dim_delta", 0) or 0) <= 0 or not toggle_regression_report.get("toggle_regression_passed"):
        status = "raw_doppler_toggle_failed"
        next_stage = "N8C4_toggle_fix"
    else:
        variants = list(variant_report.get("variants", []))
        with_raw = next((row for row in variants if row.get("variant") == "weak_yaw_smoothness_with_raw_fixed"), {})
        without_raw = next((row for row in variants if row.get("variant") == "raw_doppler_off_verified"), {})
        yaw_delta = abs(float(with_raw.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) - float(without_raw.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0))
        any_degrade = any(row.get("gross_degradation") for row in variants if row.get("raw_doppler_enabled"))
        if any_degrade:
            status = "raw_doppler_active_weight_policy_needs_review"
            next_stage = "N8D_weight_policy_review"
        elif yaw_delta < 0.05:
            status = "raw_doppler_active_consistent_or_dominated"
            next_stage = "N8D_factor_weight_policy_review"
        else:
            status = "raw_doppler_fgo_factor_activation_fixed"
            next_stage = "N8D_formal_ablation_matrix"
    figures = figure_manifest or {}
    return {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        "status": status,
        "recommended_next_stage": next_stage,
        "source_found": dataset_link_report.get("source_found"),
        "aligned_factor_count": dataset_link_report.get("aligned_factor_count", 0),
        "appears_in_solver_residual_vector": solver_injection_report.get("appears_in_solver_residual_vector"),
        "residual_row_count": solver_injection_report.get("residual_row_count", 0),
        "jacobian_nonzero_count": solver_injection_report.get("jacobian_nonzero_count", 0),
        "residual_vector_dim_delta": solver_injection_report.get("dim_delta", 0),
        "toggle_regression_passed": toggle_regression_report.get("toggle_regression_passed"),
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
        "paper_performance_claim": False,
    }
