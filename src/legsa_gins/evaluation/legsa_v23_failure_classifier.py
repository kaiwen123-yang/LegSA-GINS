"""N4H4D1 failure classifier.

中文说明：汇总 config、first-epoch、residual、isolation 证据，给出下一阶段；
只诊断，不修算法、不调参、不删除 epoch。
"""

from __future__ import annotations

from typing import Any


RECOMMENDED_STAGE = {
    "config_unit_or_initialization_issue": "N4H4D_config_unit_fix",
    "time_alignment_issue": "N4H4D_time_alignment_fix",
    "mechanization_frame_or_gravity_issue": "N4H4D_mechanization_debug",
    "position_update_sign_or_lever_issue": "N4H4D_position_update_sign_fix",
    "velocity_update_sign_issue": "N4H4D_velocity_update_sign_fix",
    "yaw_update_convention_or_initialization_issue": "N4H4D_yaw_update_convention_fix",
    "ekf_update_or_covariance_issue": "N4H4D_covariance_noise_fix",
    "state_feedback_sign_issue": "N4H4D_state_feedback_sign_fix",
    "writer_or_evaluator_convention_issue": "N4H4D_output_evaluator_fix",
    "evidence_missing": "N4H4D_instrumentation_extend",
}


def classify_failure(
    config_report: dict[str, Any],
    first_epoch_report: dict[str, Any],
    residual_report: dict[str, Any],
    isolation_report: dict[str, Any],
) -> dict[str, Any]:
    """中文说明：按优先级分类；严重全量发散时不把问题过早缩窄到 yaw。"""

    candidates: list[str] = []
    blocking_issues: list[str] = []
    if config_report.get("config_units_issue") or config_report.get("initatt_yaw_mismatch"):
        candidates.append("config_unit_or_initialization_issue")
        blocking_issues.append("config/init unit mismatch evidence")
    if first_epoch_report.get("first_epoch_time_alignment_issue"):
        candidates.append("time_alignment_issue")
        blocking_issues.append("first GNSS/IMU time alignment suspicious")
    if first_epoch_report.get("first_epoch_mechanization_jump_issue"):
        candidates.append("mechanization_frame_or_gravity_issue")
        blocking_issues.append("first propagation jump detected")
    if first_epoch_report.get("first_epoch_covariance_issue"):
        candidates.append("ekf_update_or_covariance_issue")
        blocking_issues.append("covariance abnormal in first propagation")
    residual_classes = residual_report.get("reject_reason_classification", [])
    if "position_residual_sign_or_lever_issue" in residual_classes:
        candidates.append("position_update_sign_or_lever_issue")
        blocking_issues.append("position residuals large")
    if "velocity_residual_issue" in residual_classes:
        candidates.append("velocity_update_sign_issue")
        blocking_issues.append("velocity residuals large")
    if "yaw_convention_or_init_issue" in residual_classes:
        candidates.append("yaw_update_convention_or_initialization_issue")
        blocking_issues.append("yaw residuals/rejects large")
    if "feedback_jump_issue" in residual_classes or first_epoch_report.get("first_epoch_feedback_jump_issue"):
        candidates.append("state_feedback_sign_issue")
        blocking_issues.append("dx before feedback is large")
    isolation_source = isolation_report.get("recommended_issue_source")
    if isolation_source == "likely_mechanization_or_initialization_issue":
        candidates.append("mechanization_frame_or_gravity_issue")
        blocking_issues.append("propagation-only variant diverges")
    elif isolation_source == "likely_state_feedback_sign_issue":
        candidates.append("state_feedback_sign_issue")
        blocking_issues.append("no-state-feedback variant differs from all-updates")
    elif isolation_source == "likely_position_update_sign_or_lever_issue":
        candidates.append("position_update_sign_or_lever_issue")
    elif isolation_source == "likely_yaw_update_or_feedback_issue":
        candidates.append("yaw_update_convention_or_initialization_issue")
    elif isolation_source == "evidence_missing":
        candidates.append("evidence_missing")

    priority = [
        "config_unit_or_initialization_issue",
        "time_alignment_issue",
        "mechanization_frame_or_gravity_issue",
        "state_feedback_sign_issue",
        "position_update_sign_or_lever_issue",
        "velocity_update_sign_issue",
        "yaw_update_convention_or_initialization_issue",
        "ekf_update_or_covariance_issue",
        "writer_or_evaluator_convention_issue",
        "evidence_missing",
    ]
    unique = list(dict.fromkeys(candidates)) or ["evidence_missing"]
    primary = next((item for item in priority if item in unique), unique[0])
    return {
        "phase": "N4H4D1",
        "failure_classification": primary,
        "candidate_classifications": unique,
        "recommended_next_stage": RECOMMENDED_STAGE.get(primary, "N4H4D_instrumentation_extend"),
        "blocking_issues": list(dict.fromkeys(blocking_issues)) or ["evidence_missing"],
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

