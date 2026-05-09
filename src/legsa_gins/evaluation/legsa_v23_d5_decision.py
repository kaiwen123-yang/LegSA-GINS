"""N4H4D5 decision logic."""

from __future__ import annotations

from typing import Any


def classify_d5(
    one_step_report: dict[str, Any],
    block_report: dict[str, Any],
    cov_gain_report: dict[str, Any],
    feedback_matrix_report: dict[str, Any],
    shadow_update_report: dict[str, Any],
    d4_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """中文说明：把 D5 诊断证据映射到 D6 next stage，不做 solver fix。"""

    blocking: list[str] = []
    if one_step_report.get("one_step_mechanization_suspect"):
        issue = "mechanization_step_error"
        next_stage = "N4H4D6_mechanization_step_fix"
        blocking.append("one_step_mechanization_suspect")
    elif feedback_matrix_report.get("attitude_feedback_primary_issue"):
        issue = "state_feedback_attitude_overcorrection"
        next_stage = "N4H4D6_feedback_attitude_covariance_fix"
        blocking.append("attitude_feedback_primary_issue")
    elif feedback_matrix_report.get("gain_or_R_scaling_issue") or cov_gain_report.get("gain_spike_drives_feedback"):
        issue = "covariance_or_measurement_noise_scaling"
        next_stage = "N4H4D6_covariance_measurement_noise_fix"
        blocking.append("gain_or_R_scaling_issue")
    elif feedback_matrix_report.get("velocity_update_primary_issue"):
        issue = "velocity_update_primary_issue"
        next_stage = "N4H4D6_velocity_update_fix"
        blocking.append("velocity_update_primary_issue")
    elif feedback_matrix_report.get("yaw_update_primary_issue"):
        issue = "yaw_update_primary_issue"
        next_stage = "N4H4D6_yaw_update_mapping_fix"
        blocking.append("yaw_update_primary_issue")
    elif feedback_matrix_report.get("position_update_primary_issue"):
        issue = "position_update_primary_issue"
        next_stage = "N4H4D6_position_update_fix"
        blocking.append("position_update_primary_issue")
    elif shadow_update_report.get("large_dx_caused_by_state_divergence"):
        issue = "mechanization_feedback_coupled_issue"
        next_stage = "N4H4D6_mechanization_feedback_coupled_fix"
        blocking.append("large_dx_caused_by_state_divergence")
    else:
        issue = "evidence_insufficient"
        next_stage = "N4H4D5_extend_debug"
        blocking.append("evidence_missing")
    if block_report.get("feedback_applies_large_phi"):
        blocking.append("feedback_applies_large_phi")
    if cov_gain_report.get("covariance_model_needs_unit_parity_audit"):
        blocking.append("covariance_model_needs_unit_parity_audit")
    return {
        "phase": "N4H4D5",
        "most_likely_issue": issue,
        "recommended_next_stage": next_stage,
        "blocking_issues": sorted(set(blocking)),
        "d4_context_loaded": bool(d4_report),
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "shadow_external_nav_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
