"""N8F decision policy for active legged candidate FGO factors.

中文说明：只给工程下一阶段建议，不做论文性能结论。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


def build_n8f_decision_report(
    *,
    contact_report: Mapping[str, Any],
    foot_report: Mapping[str, Any],
    yawrate_report: Mapping[str, Any],
    relative_report: Mapping[str, Any],
    contracts_report: Mapping[str, Any],
    comparison_report: Mapping[str, Any],
) -> Dict[str, Any]:
    injection_failures = list(comparison_report.get("candidate_solver_injection_failures", []))
    gross_variants = list(comparison_report.get("gross_degradation_variants", []))
    foot_active = int(foot_report.get("factor_rows", 0) or 0) > 0 and bool(foot_report.get("toggle_works", False))
    yaw_active = int(yawrate_report.get("factor_rows", 0) or 0) > 0 and bool(yawrate_report.get("toggle_works", False))
    rel_active = int(relative_report.get("factor_rows", 0) or 0) > 0 and bool(relative_report.get("toggle_works", False))
    contact_ready = int(contact_report.get("rows", 0) or 0) > 0 and float(contact_report.get("scale_p95", 0.0) or 0.0) > 0.0

    if injection_failures:
        status = "candidate_factor_solver_injection_blocker"
        next_stage = "N8F2_solver_injection_fix"
    elif foot_active and not gross_variants:
        status = "foot_kinematic_factor_ready_for_N8G_feedback_review"
        next_stage = "N8G_fgo_feedback_ekf_foundation"
    elif yaw_active and rel_active and not gross_variants:
        status = "between_factors_active_low_marginal_value"
        next_stage = "N8G_feedback_with_candidate_caveat"
    elif gross_variants:
        status = "default_stack_ready_candidates_diagnostic_only"
        next_stage = "N8G_feedback_with_default_stack"
    elif contact_ready:
        status = "contact_aware_weighting_ready"
        next_stage = "N8G_feedback_with_contact_aware_weights"
    else:
        status = "legged_candidates_active_low_marginal_value"
        next_stage = "N8G_feedback_or_N8F2_candidate_policy_review"

    return {
        "stage": "N8F",
        "status": status,
        "recommended_next_stage": next_stage,
        "candidate_solver_injection_failures": injection_failures,
        "gross_degradation_variants": gross_variants,
        "contact_aware_weighting_ready": contact_ready,
        "foot_kinematic_factor_active": foot_active,
        "yawrate_between_factor_active": yaw_active,
        "relative_odometry_between_factor_active": rel_active,
        "all_contracts_clear": bool(contracts_report.get("all_jacobian_checks_passed"))
        and bool(contracts_report.get("all_no_truth_claim"))
        and bool(contracts_report.get("all_trace_input_false"))
        and bool(contracts_report.get("all_finalv23_input_false")),
        "paper_performance_claim": False,
        "no_paper_performance_claim": True,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "finalv23_solver_input": False,
        "trace_weight_tuning": False,
        "finalv23_weight_tuning": False,
        "go2_truth_claim": False,
        "no_go2_truth_claim": True,
    }


def write_decision_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
