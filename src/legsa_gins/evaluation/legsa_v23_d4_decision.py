"""Decision rules for N4H4D4 trace parity diagnostics."""

from __future__ import annotations

from typing import Any


def classify_d4(
    external_trace_report: dict[str, Any],
    first_divergence_report: dict[str, Any],
    runtime_loop_report: dict[str, Any],
    shadow_measurement_report: dict[str, Any],
    gain_feedback_report: dict[str, Any],
    d1_report: dict[str, Any] | None = None,
    d2_report: dict[str, Any] | None = None,
    d3_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """中文说明：把 D4 证据归类到下一阶段，不做 solver fix 或性能结论。"""

    blocking: list[str] = []
    if runtime_loop_report.get("update_count_low"):
        issue = "runtime_loop_update_timing"
        next_stage = "N4H4D5_update_timeline_fix"
        blocking.append("update_count_low")
    elif shadow_measurement_report.get("measurement_model_or_convention_issue"):
        issue = "measurement_model_convention"
        next_stage = "N4H4D5_measurement_model_fix"
        blocking.append("shadow_external_state_residuals_large")
    elif first_divergence_report.get("divergence_before_first_update") and shadow_measurement_report.get(
        "measurement_model_likely_ok_state_diverges"
    ):
        issue = "mechanization_or_initial_state_propagation"
        next_stage = "N4H4D5_mechanization_step_parity"
        blocking.append("divergence_before_first_update")
    elif first_divergence_report.get("divergence_at_first_update") and (
        gain_feedback_report.get("feedback_overcorrection") or gain_feedback_report.get("kalman_gain_too_large")
    ):
        issue = "kalman_gain_or_state_feedback_overcorrection"
        next_stage = "N4H4D5_covariance_gain_feedback_fix"
        blocking.append("first_update_dx_or_gain_spike")
    elif shadow_measurement_report.get("measurement_model_likely_ok_state_diverges"):
        issue = "state_divergence_from_mechanization_or_feedback"
        next_stage = "N4H4D5_mechanization_or_feedback_isolation"
        blocking.append("internal_residuals_grow_after_state_divergence")
    else:
        issue = "evidence_insufficient"
        next_stage = "N4H4D4_extend_runtime_trace"
        blocking.append("evidence_missing")

    full_diff = external_trace_report.get("full_diff", {})
    if full_diff.get("horizontal_rmse_m") and full_diff["horizontal_rmse_m"] > 10.0:
        blocking.append("large_horizontal_trace_gap")
    if full_diff.get("yaw_rmse_deg") and full_diff["yaw_rmse_deg"] > 5.0:
        blocking.append("large_yaw_trace_gap")
    if gain_feedback_report.get("covariance_invalid"):
        blocking.append("covariance_invalid")
    return {
        "phase": "N4H4D4",
        "most_likely_issue": issue,
        "recommended_next_stage": next_stage,
        "blocking_issues": sorted(set(blocking)),
        "d1_context_loaded": bool(d1_report),
        "d2_context_loaded": bool(d2_report),
        "d3_context_loaded": bool(d3_report),
        "no_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "shadow_external_nav_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
