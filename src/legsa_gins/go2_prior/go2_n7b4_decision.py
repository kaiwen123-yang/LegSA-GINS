"""N7B4 decision logic for literature-informed Go2 diagnostics.

中文说明：decision 只给出下一阶段建议，不把 diagnostic activation 写成正式
Go2 velocity/contact prior，也不做 paper performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7b4_decision(
    *,
    contact_probability_report: dict[str, Any],
    frame_score_report: dict[str, Any],
    prior_build_report: dict[str, Any],
    activation_report: dict[str, Any],
) -> dict[str, Any]:
    contact_ready = bool(contact_probability_report.get("contact_probability_model_ready", False))
    frame_status = str(frame_score_report.get("frame_status") or "unresolved")
    frame_testable = frame_status in {"resolved_for_diagnostic", "ambiguous_but_testable"}
    frame_resolved = frame_status == "resolved_for_diagnostic"
    stable = bool(activation_report.get("stable_with_updates"))
    degraded = bool(activation_report.get("diagnostic_degradation_detected", False))
    if contact_ready and frame_resolved and stable:
        status = "ready_for_N7C_diagnostic_to_formal_go2_velocity_prior_review"
        recommended = "N7C_go2_velocity_contact_weak_prior_activation"
    elif contact_ready and frame_status == "ambiguous_but_testable":
        status = "contact_ready_frame_ambiguous"
        recommended = "N7B5_frame_resolution_or_N8A"
    elif degraded:
        status = "go2_velocity_prior_not_recommended"
        recommended = "N8A_no_feedback_FGO_foundation"
    elif not contact_ready:
        status = "go2_contact_model_not_ready"
        recommended = "N8A_no_feedback_FGO_foundation"
    elif contact_ready and frame_testable and not stable:
        status = "diagnostic_activation_no_effect_or_blocked"
        recommended = "N7B5_frame_resolution_or_N8A"
    else:
        status = "go2_contact_model_not_ready"
        recommended = "N8A_no_feedback_FGO_foundation"
    return {
        "stage": "N7B4_literature_informed_contact_velocity",
        "status": status,
        "recommended_next_stage": recommended,
        "selected_contact_probability_model": contact_probability_report.get("selected_contact_probability_model"),
        "plausible_probability_models": contact_probability_report.get("plausible_probability_models", []),
        "frame_status": frame_status,
        "selected_frame": frame_score_report.get("selected_frame_for_diagnostic"),
        "second_best_frame": frame_score_report.get("second_best"),
        "frame_margin": frame_score_report.get("margin"),
        "probability_weighted_prior_csv_generated": prior_build_report.get("csv_generated", False),
        "probability_weighted_prior_epoch_count": prior_build_report.get("epoch_count", 0),
        "stable_with_updates": activation_report.get("stable_with_updates", []),
        "diagnostic_degradation_detected": degraded,
        "paper_performance_claim": False,
        "diagnostic_only": True,
        "formal_go2_velocity_prior": False,
        "formal_go2_yaw_prior": False,
        "trace_tuning": False,
        "final_v23_tuning": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
        "no_outperform_final_v23_claim": True,
    }


def write_n7b4_decision(decision: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
