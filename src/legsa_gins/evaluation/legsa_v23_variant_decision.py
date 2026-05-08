"""N4H4D2 diagnostic decision logic.

中文说明：根据 formula audit、mechanization sanity、diagnostic variant matrix 和 D1 结果，
给出下一阶段候选修复方向；这里不直接修 solver，也不形成性能 claim。
"""

from __future__ import annotations

from typing import Any


def _variant_to_stage(variant: str | None) -> str:
    if not variant:
        return "N4H4D2_extend_instrumentation"
    mapping = {
        "position_residual_sign_flip": "N4H4D3_apply_guarded_fix_position_residual_sign_flip",
        "position_H_phi_sign_flip": "N4H4D3_apply_guarded_fix_position_H_phi_sign_flip",
        "position_no_H_phi": "N4H4D3_position_H_phi_or_feedback_fix",
        "velocity_residual_sign_flip": "N4H4D3_velocity_residual_fix",
        "yaw_residual_sign_flip": "N4H4D3_yaw_fix_after_mechanization_update_fix",
        "yaw_H_sign_flip": "N4H4D3_yaw_fix_after_mechanization_update_fix",
        "state_feedback_pos_vel_add": "N4H4D3_apply_guarded_fix_state_feedback_pos_vel_add",
        "state_feedback_phi_negative": "N4H4D3_apply_guarded_fix_state_feedback_phi_negative",
        "state_feedback_phi_right_multiply": "N4H4D3_apply_guarded_fix_state_feedback_phi_right_multiply",
        "state_feedback_no_phi": "N4H4D3_position_H_phi_or_feedback_fix",
        "ekf_update_residual_sign_flip": "N4H4D3_apply_guarded_fix_ekf_update_residual_sign_flip",
    }
    return mapping.get(variant, f"N4H4D3_apply_guarded_fix_{variant}")


def classify_d2_decision(
    formula_report: dict[str, Any],
    mech_report: dict[str, Any],
    variant_matrix: dict[str, Any],
    d1_reports: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """中文说明：输出 most_likely_issue / next_stage；variant 结果只作诊断证据。"""

    candidates = list(formula_report.get("formula_mismatch_candidates", []))
    candidate_fix_detected = bool(variant_matrix.get("candidate_fix_detected"))
    candidate_variant = variant_matrix.get("candidate_fix_variant")
    improved = list(variant_matrix.get("improved_variants", []))
    immediate_mech = bool(mech_report.get("immediate_gravity_or_frame_issue"))
    long_free_ins_only = bool(mech_report.get("long_free_ins_drift_only"))

    most_likely_issue = "evidence_missing"
    secondary_issues: list[str] = []
    recommended = "N4H4D2_extend_instrumentation"
    evidence_strength = "low"

    if candidates:
        most_likely_issue = candidates[0]
        secondary_issues.extend(candidates[1:])
        recommended = f"N4H4D3_apply_formula_parity_fix_{candidates[0]}"
        evidence_strength = "medium"
    if candidate_fix_detected:
        most_likely_issue = str(candidate_variant)
        secondary_issues.extend(item for item in improved if item != candidate_variant)
        recommended = _variant_to_stage(str(candidate_variant))
        evidence_strength = "high"
    elif immediate_mech:
        most_likely_issue = "mechanization_frame_or_gravity_issue"
        recommended = "N4H4D3_mechanization_frame_gravity_fix"
        evidence_strength = "medium"
    elif any(name in improved for name in ["position_H_phi_sign_flip", "position_no_H_phi", "state_feedback_no_phi"]):
        most_likely_issue = "position_H_phi_or_feedback_issue"
        recommended = "N4H4D3_position_H_phi_or_feedback_fix"
        evidence_strength = "medium"
    elif any(name in improved for name in ["velocity_residual_sign_flip"]):
        most_likely_issue = "velocity_residual_sign_issue"
        recommended = "N4H4D3_velocity_residual_fix"
        evidence_strength = "medium"
    elif any(name in improved for name in ["yaw_residual_sign_flip", "yaw_H_sign_flip"]):
        most_likely_issue = "yaw_update_convention_secondary"
        recommended = "N4H4D3_yaw_fix_after_mechanization_update_fix"
        evidence_strength = "medium"
    elif long_free_ins_only:
        most_likely_issue = "time_alignment_or_hidden_config_or_coupled_update_issue"
        recommended = "N4H4D2_extend_instrumentation"
        evidence_strength = "low"

    blocking = [
        "baseline_current parity failed",
        "diagnostic variants are not formal results",
    ]
    if variant_matrix.get("multi_issue_or_coupled_issue"):
        blocking.append("multiple variants improve, coupled issue likely")
    if d1_reports and d1_reports.get("yaw_reject_ratio", 0.0) > 0.5:
        blocking.append("yaw rejects remain high in D1 evidence")

    return {
        "phase": "N4H4D2",
        "most_likely_issue": most_likely_issue,
        "secondary_issues": sorted(set(secondary_issues)),
        "evidence_strength": evidence_strength,
        "recommended_next_stage": recommended,
        "blocking_issues": blocking,
        "candidate_fix_detected": candidate_fix_detected,
        "candidate_fix_variant": candidate_variant,
        "multi_issue_or_coupled_issue": bool(variant_matrix.get("multi_issue_or_coupled_issue")),
        "no_performance_claim": True,
        "diagnostic_only": True,
        "not_for_performance_claim": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
