"""N7A Go2 weak-prior decision rules.

中文说明：决策只界定工程状态和下一阶段；不做 paper performance claim，也不声称
outperform final_v23。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_go2_weak_prior_decision(
    *,
    build_report: dict[str, Any],
    frame_report: dict[str, Any],
    comparison_report: dict[str, Any],
    source_aware_stats: dict[str, Any],
) -> dict[str, Any]:
    go2_manifest = comparison_report.get("go2_attitude_weak_prior_manifest", {})
    update_count = int(go2_manifest.get("go2_attitude_weak_prior_update_count", 0) or 0)
    clean_delta = comparison_report.get("go2_attitude_weak_prior_minus_no_go2", {}).get("delta", {})
    gross_degrade = any(
        (clean_delta.get(key) is not None and clean_delta[key] > limit)
        for key, limit in {
            "horizontal_rmse_m": 0.5,
            "up_rmse_m": 0.5,
            "yaw_rmse_deg": 0.5,
            "roll_rmse_deg": 0.2,
            "pitch_rmse_deg": 0.2,
        }.items()
    )
    roll_pitch_stable = not any(
        (clean_delta.get(key) is not None and clean_delta[key] > 0.15)
        for key in ["roll_rmse_deg", "pitch_rmse_deg"]
    )
    if update_count == 0:
        status = "not_activated"
        next_stage = "N7B_go2_prior_activation_fix"
    elif not frame_report.get("activation_allowed"):
        status = "frame_contract_issue"
        next_stage = "N7B_go2_attitude_frame_resolution"
    elif gross_degrade:
        status = "needs_prior_noise_policy_fix"
        next_stage = "N7B_go2_prior_noise_policy_refinement"
    elif roll_pitch_stable and source_aware_stats.get("go2_source_seen"):
        status = "ready_for_extended_go2_priors_or_FGO_preparation"
        next_stage = "N7B_go2_velocity_contact_readiness_or_N8A_no_feedback_FGO_foundation"
    else:
        status = "ready_with_weak_go2_evidence"
        next_stage = "N7B_go2_velocity_contact_readiness"
    return {
        "stage": "N7A_go2_body_state_weak_prior_foundation",
        "status": status,
        "recommended_next_stage": next_stage,
        "go2_attitude_weak_prior_update_count": update_count,
        "go2_attitude_weak_prior_reject_count": int(go2_manifest.get("go2_attitude_weak_prior_reject_count", 0) or 0),
        "activation_allowed": bool(build_report.get("activation_allowed")),
        "frame_activation_allowed": bool(frame_report.get("activation_allowed")),
        "clean_delta": clean_delta,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }


def write_go2_weak_prior_decision(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
