"""N4H4D6 decision logic."""

from __future__ import annotations

from typing import Any


def classify_d6(
    imu_error_feedback_report: dict[str, Any],
    compensation_timing_report: dict[str, Any],
    covariance_unit_report: dict[str, Any],
    variant_matrix_report: dict[str, Any],
    d5_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """中文说明：把 D6 证据映射到 D7 next stage；不做算法修复或性能声明。"""

    blocking: list[str] = []
    if compensation_timing_report.get("repeated_compensation_issue") or compensation_timing_report.get(
        "repeated_compensation_detected"
    ) or compensation_timing_report.get("compensation_not_persistent_issue"):
        issue = "imu_compensation_repeated_or_not_persistent"
        next_stage = "N4H4D7_fix_imu_compensation_timing"
        blocking.append("imu_compensation_timing_issue")
    elif variant_matrix_report.get("bias_scale_feedback_primary_suspect") and covariance_unit_report.get(
        "covariance_unit_mismatch_suspect"
    ):
        issue = "bias_scale_feedback_covariance_unit_coupling"
        next_stage = "N4H4D7_fix_bias_scale_covariance_units"
        blocking.extend(["bias_scale_feedback_primary_suspect", "covariance_unit_mismatch_suspect"])
    elif variant_matrix_report.get("bias_scale_feedback_primary_suspect"):
        issue = "bias_scale_feedback_coupling"
        next_stage = "N4H4D7_guard_bias_scale_feedback_coupling"
        blocking.append("bias_scale_feedback_primary_suspect")
    elif variant_matrix_report.get("pos_vel_attitude_only_improves_over_normal"):
        issue = "bias_scale_feedback_source_backed_fix_needed"
        next_stage = "N4H4D7_disable_or_fix_bias_scale_feedback_source_backed"
        blocking.append("pos_vel_attitude_only_improves_over_normal")
    elif variant_matrix_report.get("best_diagnostic_variant") == "pos_vel_only":
        issue = "attitude_feedback_coupling"
        next_stage = "N4H4D7_attitude_feedback_coupling_fix"
        blocking.append("pos_vel_only_best_variant")
    elif compensation_timing_report.get("compensation_timing_ok") and not variant_matrix_report.get(
        "bias_scale_feedback_primary_suspect"
    ):
        issue = "covariance_cross_coupling"
        next_stage = "N4H4D7_covariance_cross_coupling_fix"
        blocking.append("bias_scale_variants_not_decisive")
    else:
        issue = "evidence_insufficient"
        next_stage = "N4H4D6_extend_instrumentation"
        blocking.append("evidence_missing")
    if imu_error_feedback_report.get("bias_feedback_overcorrection"):
        blocking.append("bias_feedback_overcorrection")
    if imu_error_feedback_report.get("scale_feedback_overcorrection"):
        blocking.append("scale_feedback_overcorrection")
    if covariance_unit_report.get("P_phi_bias_cross_cov_large"):
        blocking.append("P_phi_bias_cross_cov_large")
    return {
        "phase": "N4H4D6",
        "most_likely_issue": issue,
        "recommended_next_stage": next_stage,
        "blocking_issues": sorted(set(blocking)),
        "d5_context_loaded": bool(d5_report),
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

