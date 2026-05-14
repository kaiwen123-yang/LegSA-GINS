"""N8E module contribution summary.

中文说明：模块贡献只做工程归纳，低边际贡献不写成失败。
"""

from __future__ import annotations

from typing import Any


def _status(report: dict[str, Any], default: str) -> str:
    return str(report.get("status") or report.get("decision_status") or default)


def build_module_contribution_summary(
    *,
    stage_reports: dict[str, dict[str, Any]],
    matrix_report: dict[str, Any],
) -> dict[str, Any]:
    n5b = stage_reports.get("n5b_decision", {})
    n6b = stage_reports.get("n6b_decision", {})
    n7c6 = stage_reports.get("n7c6_decision", {})
    n8c3 = stage_reports.get("n8c3_decision", {})
    n8d = stage_reports.get("n8d_decision", {})
    raw_receiver = stage_reports.get("n8d_raw_receiver", {})

    modules = [
        {
            "module": "Raw Doppler EKF",
            "status": "active_effective_frontend_factor",
            "evidence": ["N5B", "N5D", "N5C", _status(n5b, "raw_doppler_frontend_active")],
            "caveat": "Raw Doppler FGO marginal value is low in N8D, but this is not EKF activation failure.",
            "low_marginal_value_is_failure": False,
        },
        {
            "module": "Raw Doppler FGO",
            "status": "active_solver_factor_low_marginal_value",
            "evidence": ["N8C3", "N8D", _status(n8c3, "raw_doppler_active_consistent_or_dominated")],
            "caveat": "Active solver factor, but current no-feedback FGO marginal value is low and appears consistent with receiver velocity/smoothness dominance.",
            "raw_doppler_remains_low_marginal_value": bool(
                raw_receiver.get("raw_doppler_remains_low_marginal_value")
                or n8d.get("raw_doppler_remains_low_marginal_value")
            ),
            "low_marginal_value_is_failure": False,
        },
        {
            "module": "Source-aware LSIM/OIM",
            "status": "active_R_scaling_layer",
            "evidence": ["N6B", "N6B1", _status(n6b, "ready_with_weak_stress_evidence")],
            "caveat": "Stress evidence remains limited; do not overstate generalization.",
        },
        {
            "module": "Go2 proprioceptive joint",
            "status": "active_EKF_factor",
            "evidence": ["N7C6", _status(n7c6, "go2_joint_factor_review_passed")],
            "caveat": "Small but stable deltas; Go2 fields are proprioceptive observations, not truth.",
        },
        {
            "module": "Contact probability",
            "status": "weighting_candidate",
            "evidence": ["N7C5", "N8C"],
            "caveat": "Contact probability is not a direct factor in the formal stack.",
        },
        {
            "module": "Foot kinematic velocity",
            "status": "diagnostic_candidate",
            "evidence": ["N7C5"],
            "caveat": "High slip risk; needs FGO-specific review before promotion.",
        },
        {
            "module": "Yaw-rate / relative odometry",
            "status": "FGO_candidate",
            "evidence": ["N7C5", "N8B"],
            "caveat": "Diagnostic only; not a formal factor in N8E.",
        },
        {
            "module": "no-feedback FGO",
            "status": "framework_ready",
            "evidence": ["N8A2", "N8B", "N8D"],
            "caveat": "No feedback/substitution, no trace/final_v23 tuning, no paper performance claim.",
        },
    ]
    return {
        "stage": "N8E_formal_engineering_ablation_with_caveat",
        "modules": modules,
        "module_count": len(modules),
        "matrix_complete": bool(matrix_report.get("matrix_complete")),
        "raw_doppler_low_marginal_value_is_not_failure": True,
        "candidate_factors_diagnostic_only": True,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }
