"""N7B Go2 velocity/contact readiness decision.

中文说明：decision 只推荐未来阶段，N7B 本身不启用 velocity/yaw prior 和 FGO。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7b_decision(
    *,
    contact_report: dict[str, Any],
    velocity_report: dict[str, Any],
    yaw_rate_report: dict[str, Any],
    motion_report: dict[str, Any] | None = None,
    n7a_weak_prior_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contact_status = contact_report.get("recommended_contact_quality_status")
    velocity_status = velocity_report.get("consistency_status")
    yaw_status = yaw_rate_report.get("consistency_status")
    n7a_activation_allowed = bool((n7a_weak_prior_report or {}).get("activation_allowed", True))
    if contact_status == "not_ready" or float(contact_report.get("uncertain_ratio", 1.0) or 1.0) > 0.60:
        status = "contact_not_ready"
        recommended = "N7B2_contact_threshold_review"
    elif velocity_status == "strongly_inconsistent":
        status = "velocity_not_ready"
        recommended = "N7B2_velocity_frame_or_quality_review"
    elif contact_status == "ready" and velocity_status == "acceptable_for_future_review":
        status = "ready_for_go2_velocity_weak_prior_activation"
        recommended = "N7C_go2_velocity_contact_weak_prior_activation"
    elif yaw_rate_report.get("yaw_rate_prior_recommended") == "conditional":
        status = "ready_for_go2_yaw_rate_prior_review"
        recommended = "N7C_go2_yaw_rate_weak_prior_review"
    elif n7a_activation_allowed:
        status = "skip_extended_go2_priors_prepare_FGO"
        recommended = "N8A_no_feedback_FGO_foundation"
    else:
        status = "velocity_not_ready"
        recommended = "N7B2_velocity_frame_or_quality_review"
    return {
        "stage": "N7B_go2_velocity_contact_readiness",
        "status": status,
        "recommended_next_stage": recommended,
        "contact_quality_status": contact_status,
        "velocity_consistency_status": velocity_status,
        "yaw_rate_consistency_status": yaw_status,
        "motion_summary": motion_report or {},
        "paper_performance_claim": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "cross_source_velocity_truth_error_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
        "no_outperform_final_v23_claim": True,
        "n7b_readiness_only": True,
    }


def write_n7b_decision(decision: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
