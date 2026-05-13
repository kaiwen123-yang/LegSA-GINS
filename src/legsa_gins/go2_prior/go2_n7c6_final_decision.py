"""N7C6A final ready-to-merge decision.

中文说明：只根据 review/audit 报告做合并门禁判断，不改 solver、不调参。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import write_json


def make_n7c6a_final_decision(
    *,
    input_manifest: dict[str, Any],
    semantic_report: dict[str, Any],
    readability_report: dict[str, Any],
    figure_manifest: dict[str, Any],
    n7c6_decision: dict[str, Any],
    nis_report: dict[str, Any],
) -> dict[str, Any]:
    blocker_reasons: list[str] = []
    if semantic_report.get("metric_semantic_status") not in {"passed", "passed_with_runtime_replacements"}:
        blocker_reasons.append("metric_semantics_ambiguous")
    if not figure_manifest.get("required_figures_generated") or not figure_manifest.get("required_figures_nonempty"):
        blocker_reasons.append("mandatory_readable_figures_missing_or_empty")
    if not input_manifest.get("n7c6_reports_all_found"):
        blocker_reasons.append("n7c6_reports_missing")
    if n7c6_decision.get("status") not in {
        "go2_proprioceptive_joint_factor_ready",
        "stronger_go2_proprioceptive_joint_factor_ready",
        "horizontal_factor_sufficient",
    }:
        blocker_reasons.append("n7c6_decision_not_ready")
    if nis_report.get("any_overconfidence") or nis_report.get("any_stuck_at_cap"):
        blocker_reasons.append("nis_or_sourceaware_boundary_failed")
    if input_manifest.get("go2_position_prior_enabled") or input_manifest.get("go2_yaw_prior_enabled") or input_manifest.get("go2_vertical_velocity_prior_enabled"):
        blocker_reasons.append("go2_position_yaw_vertical_prior_enabled")

    if "metric_semantics_ambiguous" in blocker_reasons:
        status = "n7c6_not_ready_metric_semantics"
        next_stage = "N7C6B_metric_semantics_fix"
    elif "mandatory_readable_figures_missing_or_empty" in blocker_reasons:
        status = "n7c6_not_ready_visual_figures"
        next_stage = "N7C6B_visual_fix"
    elif "n7c6_decision_not_ready" in blocker_reasons:
        status = "n7c6_not_ready_result_mismatch"
        next_stage = "N7C6B_result_recheck"
    elif blocker_reasons:
        status = "n7c6_not_ready_result_mismatch"
        next_stage = "N7C6B_result_recheck"
    else:
        status = "ready_to_merge_PR38_and_start_N8A"
        next_stage = "N8A_no_feedback_FGO_foundation"

    return {
        "stage": "N7C6A_go2_proprioceptive_joint_final_review",
        "status": status,
        "recommended_next_stage": next_stage,
        "blocker_reasons": blocker_reasons,
        "metric_semantic_status": semantic_report.get("metric_semantic_status"),
        "plot_label_readability_status": readability_report.get("plot_label_readability_status"),
        "replacement_figures_generated": bool(figure_manifest.get("required_figures_generated")),
        "replacement_figures_nonempty": bool(figure_manifest.get("required_figures_nonempty")),
        "n7c6_decision_status": n7c6_decision.get("status"),
        "recommended_default": n7c6_decision.get("recommended_default"),
        "any_overconfidence": bool(nis_report.get("any_overconfidence")),
        "any_stuck_at_cap": bool(nis_report.get("any_stuck_at_cap")),
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_not_truth": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "fgo": False,
        "output_only_correction": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_n7c6a_final_decision(path: str, decision: dict[str, Any]):
    return write_json(path, decision)
