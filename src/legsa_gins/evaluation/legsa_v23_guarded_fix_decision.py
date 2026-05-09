"""Decision logic for N4H4D3 guarded formula fix replay."""

from __future__ import annotations

from typing import Any


def make_guarded_fix_decision(
    audit_report: dict[str, Any],
    replay_report: dict[str, Any],
    d2_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """中文说明：按 source audit 和 replay status 决定下一阶段，不做性能 claim。"""

    audit_passed = audit_report.get("audit_status") == "passed"
    summary = replay_report.get("summary", {})
    status = summary.get("guarded_fix_parity_status")
    gap = replay_report.get("gap_screen", {})
    d2 = d2_report or {}
    if not audit_passed:
        recommended = "N4H4D3_fix_source_backed_formula_implementation"
    elif status == "passed":
        recommended = "N4H4E_visual_validation_for_legsa_v23_core"
    elif status == "partial_improvement":
        categories = set(gap.get("gap_classification", []))
        if "runtime" in categories and "yaw_H_mapping" in str(d2):
            recommended = "N4H4D4_remaining_yaw_or_update_fix"
        else:
            recommended = "N4H4D4_remaining_yaw_or_update_fix"
    elif status == "no_improvement":
        recommended = "N4H4D4_revisit_mechanization_or_time_alignment"
    else:
        recommended = "N4H4D4_covariance_or_runtime_failure_debug"
    blockers = list(gap.get("blocking_issues", []))
    if audit_report.get("yaw_H_mapping_secondary_issue"):
        blockers.append("yaw_H_mapping_deferred_secondary_issue")
    if d2.get("multi_issue_or_coupled_issue"):
        blockers.append("D2_multi_issue_or_coupled_issue")
    return {
        "phase": "N4H4D3",
        "audit_passed": audit_passed,
        "guarded_fix_parity_status": status,
        "recommended_next_stage": recommended,
        "blocking_issues": list(dict.fromkeys(blockers)),
        "remaining_gap_categories": gap.get("gap_classification", []),
        "no_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
