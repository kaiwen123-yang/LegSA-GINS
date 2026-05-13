"""N7B3 diagnostic decision logic for Go2 contact/velocity activation.

中文说明：decision 只决定 N7C/N7B4/N8A 下一阶段建议，不把 diagnostic activation
升级为正式 Go2 velocity/yaw prior。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7b3_decision(
    *,
    velocity_frame_report: dict[str, Any],
    contact_model_report: dict[str, Any],
    velocity_prior_report: dict[str, Any],
    yaw_rate_prior_report: dict[str, Any],
    activation_report: dict[str, Any],
) -> dict[str, Any]:
    frame_status = str(velocity_frame_report.get("frame_ambiguity_status", ""))
    frame_resolved = bool(velocity_frame_report.get("recommended_frame_for_diagnostic_prior")) and frame_status != "ambiguous_close_candidates"
    contact_ready = bool(contact_model_report.get("contact_model_ready", False))
    degraded = bool(activation_report.get("diagnostic_degradation_detected", False))
    stable_with_updates = bool(activation_report.get("stable_with_updates"))
    if not contact_ready and not frame_resolved:
        status = "go2_velocity_contact_not_ready"
        recommended = "N8A_no_feedback_FGO_foundation"
    elif frame_resolved and not contact_ready:
        status = "velocity_frame_ready_contact_not_ready"
        recommended = "N7B4_velocity_only_weak_prior_review_or_N8A"
    elif degraded:
        status = "diagnostic_activation_degraded"
        recommended = "N8A_no_feedback_FGO_foundation_or_N7B4_model_review"
    elif contact_ready and stable_with_updates:
        status = "ready_for_N7C_go2_velocity_contact_weak_prior_activation"
        recommended = "N7C_go2_velocity_contact_weak_prior_activation"
    else:
        status = "go2_velocity_contact_not_ready"
        recommended = "N7B4_model_review_or_N8A"
    secondary = ""
    if yaw_rate_prior_report.get("prior_epoch_count", 0) and yaw_rate_prior_report.get("activation_status") == "yaw_rate_prior_not_activated_due_to_state_model":
        secondary = "N7C_go2_yaw_rate_prior_review"
    return {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "status": status,
        "recommended_next_stage": recommended,
        "secondary_recommendation": secondary,
        "frame_ambiguity_status": frame_status,
        "selected_frame": velocity_frame_report.get("recommended_frame_for_diagnostic_prior"),
        "contact_model_ready": contact_ready,
        "selected_diagnostic_contact_model": contact_model_report.get("selected_diagnostic_contact_model"),
        "velocity_prior_csv_generated": velocity_prior_report.get("prior_csv_generated", False),
        "contact_gated_epoch_count": velocity_prior_report.get("contact_gated_epoch_count", 0),
        "yaw_rate_prior_status": yaw_rate_prior_report.get("activation_status"),
        "diagnostic_degradation_detected": degraded,
        "stable_with_updates": activation_report.get("stable_with_updates", []),
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "diagnostic_only": True,
        "output_only_correction": False,
        "trace_tuning": False,
        "final_v23_tuning": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_position_truth_claim": False,
        "go2_yaw_prior_enabled": False,
        "formal_go2_velocity_prior_enabled": False,
        "fgo": False,
        "no_outperform_final_v23_claim": True,
    }


def write_n7b3_decision(decision: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
