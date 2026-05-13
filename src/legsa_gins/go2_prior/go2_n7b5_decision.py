"""N7B5 decision logic for Go2 horizontal velocity diagnostics.

中文说明：N7B5 decision 只决定是否进入下一阶段 formal review；本阶段本身不把
horizontal Go2 velocity diagnostic 写成正式 prior，也不做 paper performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7b5_decision(
    *,
    frame_equivalence_report: dict[str, Any],
    prior_build_report: dict[str, Any],
    activation_report: dict[str, Any],
) -> dict[str, Any]:
    equivalent = bool(frame_equivalence_report.get("frame_equivalent_for_horizontal_only", False))
    stable_horizontal = bool(activation_report.get("stable_horizontal_variants"))
    degraded = bool(activation_report.get("diagnostic_degradation_detected", False))
    total_updates = int(activation_report.get("total_go2_velocity_prior_update_count", 0) or 0)
    prior_generated = bool(prior_build_report.get("csv_generated", False))
    if degraded:
        status = "go2_velocity_prior_not_recommended"
        recommended = "N8A_no_feedback_FGO_foundation"
    elif total_updates == 0 or not prior_generated:
        status = "diagnostic_activation_failed"
        recommended = "N7B6_activation_debug_or_N8A"
    elif equivalent and stable_horizontal:
        status = "ready_for_N7C_horizontal_go2_velocity_weak_prior"
        recommended = "N7C_go2_horizontal_velocity_weak_prior_activation"
    elif stable_horizontal:
        status = "ready_for_N7C_best_frame_diagnostic_review"
        recommended = "N7C_go2_best_frame_velocity_weak_prior_review"
    else:
        status = "diagnostic_activation_failed"
        recommended = "N7B6_activation_debug_or_N8A"
    return {
        "stage": "N7B5_go2_velocity_frame_horizontal_diagnostic",
        "status": status,
        "recommended_next_stage": recommended,
        "frame_equivalent_for_horizontal_only": equivalent,
        "vertical_component_ambiguous": bool(frame_equivalence_report.get("vertical_component_ambiguous", False)),
        "recommended_horizontal_policy": frame_equivalence_report.get("recommended_horizontal_policy"),
        "primary_frame": frame_equivalence_report.get("primary_frame"),
        "secondary_frame": frame_equivalence_report.get("secondary_frame"),
        "top_candidate_difference": frame_equivalence_report.get("top_candidate_difference", {}),
        "horizontal_prior_csv_generated": prior_generated,
        "horizontal_prior_epoch_count": prior_build_report.get("epoch_count", 0),
        "contact_weighted_horizontal_prior_epoch_count": prior_build_report.get("contact_weighted_epoch_count", 0),
        "vertical_velocity_disabled": prior_build_report.get("vertical_velocity_disabled", True),
        "stable_horizontal_variants": activation_report.get("stable_horizontal_variants", []),
        "stable_with_updates": activation_report.get("stable_with_updates", []),
        "total_go2_velocity_prior_update_count": total_updates,
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


def write_n7b5_decision(decision: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
