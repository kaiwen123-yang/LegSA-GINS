"""N7B2A decision rules for metric namespace and contact sanity review.

中文说明：决策只给出 readiness 结论，不启用 Go2 velocity/yaw prior，也不实现 FGO。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7b2a_decision(
    *,
    attitude_std_report: dict[str, Any],
    metric_namespace_report: dict[str, Any],
    contact_physical_report: dict[str, Any],
) -> dict[str, Any]:
    metric_missing = bool(metric_namespace_report.get("metric_namespace_missing"))
    contact_status = str(contact_physical_report.get("physical_plausibility_status", "review_or_not_ready"))
    velocity_status = str(contact_physical_report.get("velocity_segment_readiness_status", "unknown"))
    std_status = str(attitude_std_report.get("std_policy_status", "unknown"))
    if metric_missing:
        status = "needs_metric_namespace_fix"
        next_stage = "N7B2B_metric_namespace_report_fix"
    elif contact_status in {"review", "review_or_not_ready", "not_ready"}:
        status = "contact_v2_not_ready"
        next_stage = "N7B3_contact_model_review_or_N8A_no_feedback_FGO_foundation"
    elif std_status != "clear":
        status = "needs_attitude_std_policy_review"
        next_stage = "N7B2B_attitude_prior_std_review"
    elif contact_status == "plausible" and velocity_status == "acceptable":
        status = "ready_for_go2_velocity_contact_weak_prior_activation"
        next_stage = "N7C_go2_velocity_contact_weak_prior_activation"
    else:
        status = "contact_v2_not_ready"
        next_stage = "N7B3_contact_model_review_or_N8A_no_feedback_FGO_foundation"
    return {
        "stage": "N7B2A_go2_metric_contact_visual_audit",
        "status": status,
        "recommended_next_stage": next_stage,
        "metric_namespace_missing": metric_missing,
        "attitude_std_policy_status": std_status,
        "contact_physical_plausibility_status": contact_status,
        "velocity_segment_readiness_status": velocity_status,
        "all_contact_suspect": bool(contact_physical_report.get("all_contact_suspect")),
        "contact_too_permissive": bool(contact_physical_report.get("contact_too_permissive")),
        "alternating_contact_ratio": contact_physical_report.get("alternating_contact_ratio"),
        "paper_performance_claim": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
        "no_outperform_final_v23_claim": True,
        "n7b2a_review_only": True,
    }


def write_n7b2a_decision(decision: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
