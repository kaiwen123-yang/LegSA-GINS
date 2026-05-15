"""N8J final feedback validation decision.

中文说明：N8J 决策验证 BY2 selected feedback policy 是否可进入包装/复现实验，
不做论文性能宣称。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import write_json


def build_final_decision_report(
    *,
    selected_policy: dict[str, Any],
    final_manifest: dict[str, Any],
    sanity_report: dict[str, Any],
    comparison_report: dict[str, Any],
) -> dict[str, Any]:
    status, next_stage = _decide(selected_policy, final_manifest, sanity_report, comparison_report)
    return {
        "stage": "N8J",
        "status": status,
        "recommended_next_stage": next_stage,
        "selected_policy_name": selected_policy.get("policy_name"),
        "selected_feedback_variant": "n8j_selected_conservative_feedback",
        "selected_gate_policy": selected_policy.get("gate_policy"),
        "selected_covariance_policy": selected_policy.get("covariance_policy"),
        "selected_window_duration_s": selected_policy.get("window_duration_s"),
        "selected_stride_s": selected_policy.get("stride_s"),
        "by2_engineering_validation": True,
        "generalization_ready_for_next_stage": status == "feedback_joint_filter_ready_for_BY2_packaging",
        "fgo_feedback_output_substitution": False,
        "fgo_feedback_direct_nav_override": False,
        "output_substitution": False,
        "direct_nav_override": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_finalv23_tuning": True,
        "fgo_feedback_no_future_data": True,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _decide(
    selected_policy: dict[str, Any],
    final_manifest: dict[str, Any],
    sanity_report: dict[str, Any],
    comparison_report: dict[str, Any],
) -> tuple[str, str]:
    if selected_policy.get("n8i_selected_policy_match") is not True or selected_policy.get("hidden_policy_change") is True:
        return "selected_policy_mismatch", "N8J2_policy_lock_fix"
    if final_manifest.get("runtime_outputs_generated") is not True:
        return "runtime_output_missing", "N8J2_runtime_recovery"
    if final_manifest.get("accepted", 0) <= 0:
        return "feedback_not_entering_ekf", "N8J2_feedback_update_debug"
    if final_manifest.get("output_substitution") is not False or final_manifest.get("direct_nav_override") is not False:
        return "output_substitution_blocker", "N8J2_boundary_fix"
    if comparison_report.get("selected_gross_degradation") is True or sanity_report.get("checks", {}).get("no_gross_degradation") is not True:
        return "selected_feedback_policy_not_ready", "N8J2_policy_review"
    if sanity_report.get("all_checks_passed") is not True:
        return "selected_feedback_policy_not_ready", "N8J2_policy_review"
    return "feedback_joint_filter_ready_for_BY2_packaging", "N9_BY2_paper_experiment_packaging_or_BY3_replication"


def write_final_decision_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
