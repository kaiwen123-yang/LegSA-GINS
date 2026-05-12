"""N7B2 Go2 contact-threshold decision.

中文说明：decision 只判断是否具备未来 N7C review 条件；N7B2 不激活
Go2 velocity/yaw prior，不实现 FGO。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _ratio(value: Any, fallback: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def make_n7b2_decision(
    *,
    distribution_report: dict[str, Any],
    contact_v2_report: dict[str, Any],
    smoothing_report: dict[str, Any],
    velocity_segment_report: dict[str, Any],
) -> dict[str, Any]:
    field_status = distribution_report.get("field_quality_status")
    uncertain_after = _ratio(
        smoothing_report.get("uncertain_ratio_after", contact_v2_report.get("uncertain_ratio")),
        1.0,
    )
    contact_status = contact_v2_report.get("contact_quality_status")
    velocity_status = velocity_segment_report.get("readiness_status")
    if field_status not in {"usable", "unknown"}:
        status = "foot_force_field_not_reliable"
        recommended = "N8A_no_feedback_FGO_foundation"
    elif uncertain_after > 0.50:
        status = "contact_still_not_ready"
        recommended = "N8A_no_feedback_FGO_foundation_or_N7B3_contact_model_review"
    elif contact_status == "ready" and velocity_status == "acceptable":
        status = "ready_for_go2_velocity_contact_weak_prior_activation"
        recommended = "N7C_go2_velocity_contact_weak_prior_activation"
    elif contact_status == "ready":
        status = "contact_ready_velocity_not_ready"
        recommended = "N7C_yaw_rate_or_contact_only_prior_review_or_N8A"
    else:
        status = "contact_still_not_ready"
        recommended = "N8A_no_feedback_FGO_foundation_or_N7B3_contact_model_review"
    return {
        "stage": "N7B2_go2_contact_threshold_review",
        "status": status,
        "recommended_next_stage": recommended,
        "field_quality_status": field_status,
        "contact_quality_status": contact_status,
        "velocity_segment_readiness_status": velocity_status,
        "uncertain_ratio_after": uncertain_after,
        "paper_performance_claim": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "contact_conditioned_velocity_truth_error_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
        "no_outperform_final_v23_claim": True,
        "n7b2_readiness_only": True,
    }


def write_n7b2_decision(decision: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
