"""N8A1 decision rules.

中文说明：本模块按阻塞优先级给出 N8A1 审查结论。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_yaw_convention_audit import write_json_report


def make_n8a1_decision(
    *,
    yaw_convention: dict[str, Any],
    state_epoch_mapping: dict[str, Any],
    factor_policy: dict[str, Any],
    yaw_diagnostics: dict[str, Any],
    ablation: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    blocker_reasons: list[str] = []
    if yaw_convention.get("blocker_status") not in {None, "clear"}:
        status = "fgo_yaw_convention_blocker"
        recommended_next_stage = "N8A2_yaw_convention_fix"
        blocker_reasons.append(str(yaw_convention.get("blocker_status")))
    elif state_epoch_mapping.get("blocker_status") != "clear":
        status = "fgo_state_epoch_mapping_blocker"
        recommended_next_stage = "N8A2_state_mapping_fix"
        blocker_reasons.extend(state_epoch_mapping.get("blocker_reasons", []))
    elif factor_policy.get("candidate_factor_leak_suspect"):
        status = "fgo_candidate_factor_leak_blocker"
        recommended_next_stage = "N8A2_factor_registry_fix"
        blocker_reasons.append("candidate_factor_leak_suspect")
    elif factor_policy.get("smoothness_weight_suspect") or factor_policy.get("yaw_factor_weight_suspect"):
        status = "fgo_factor_weight_policy_review_needed"
        recommended_next_stage = "N8B_factor_graph_policy_review"
        if factor_policy.get("smoothness_weight_suspect"):
            blocker_reasons.append("smoothness_weight_suspect")
        if factor_policy.get("yaw_factor_weight_suspect"):
            blocker_reasons.append("yaw_factor_weight_suspect")
    elif yaw_convention.get("yaw_delta_rmse_after_best_wrap", 0.0) <= 5.0:
        status = "n8a_foundation_ready_metric_wrap_fixed"
        recommended_next_stage = "N8B_visual_validation_and_ablation"
    elif yaw_diagnostics.get("yaw_delta_rmse_wrapped_deg", 0.0) > 10.0:
        status = "n8a_foundation_ready_with_yaw_policy_caveat"
        recommended_next_stage = "N8B_factor_graph_policy_review"
        blocker_reasons.append("large_yaw_delta_explained")
    else:
        status = "n8a_foundation_ready_with_yaw_policy_caveat"
        recommended_next_stage = "N8B_factor_graph_policy_review"
    return {
        "stage": "N8A1_fgo_yaw_delta_policy_review",
        "status": status,
        "recommended_next_stage": recommended_next_stage,
        "blocker_reasons": blocker_reasons,
        "yaw_convention_blocker_status": yaw_convention.get("blocker_status"),
        "state_epoch_mapping_status": state_epoch_mapping.get("blocker_status"),
        "factor_policy_candidate_leak_suspect": factor_policy.get("candidate_factor_leak_suspect"),
        "factor_policy_smoothness_weight_suspect": factor_policy.get("smoothness_weight_suspect"),
        "factor_policy_yaw_factor_weight_suspect": factor_policy.get("yaw_factor_weight_suspect"),
        "yaw_delta_rmse_after_best_wrap": yaw_convention.get("yaw_delta_rmse_after_best_wrap"),
        "yaw_delta_primary_hypothesis": yaw_diagnostics.get("primary_hypothesis"),
        "ablation_best_yaw_delta_variant": ablation.get("best_yaw_delta_variant"),
        "ablation_best_yaw_delta_rmse_deg": ablation.get("best_yaw_delta_rmse_deg"),
        "figure_count_total": figures.get("figure_count_total", 0),
        "required_figures_generated": figures.get("required_figures_generated", False),
        "required_figures_nonempty": figures.get("required_figures_nonempty", False),
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_replaces_ekf_nav": False,
        "output_only_correction": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "audit_only": True,
    }


def write_n8a1_decision(path: str | Path, decision: dict[str, Any]) -> Path:
    return write_json_report(path, decision)
