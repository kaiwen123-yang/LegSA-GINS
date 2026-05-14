"""Decision rules for N8G feedback EKF foundation.

中文说明：决策只总结工程诊断证据，不形成论文性能 claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_n8g_decision_report(
    *,
    observation_report: dict[str, Any],
    variant_report: dict[str, Any],
    evaluation_report: dict[str, Any],
) -> dict[str, Any]:
    feedback_rows = int(observation_report.get("feedback_rows", 0) or 0)
    total_updates = int(variant_report.get("feedback_update_count_total", 0) or 0)
    total_accept = int(variant_report.get("feedback_accept_count_total", 0) or 0)
    total_reject = int(variant_report.get("feedback_reject_count_total", 0) or 0)
    gross_degrades = evaluation_report.get("gross_degradation_status") == "present"
    if feedback_rows <= 0:
        status = "feedback_observation_build_failed"
        next_stage = "N8G2_feedback_observation_fix"
    elif total_updates <= 0:
        status = "feedback_not_entering_ekf"
        next_stage = "N8G2_cpp_feedback_interface_fix"
    elif total_accept <= 0 and total_reject > 0:
        status = "feedback_gate_too_strict_or_fgo_unstable"
        next_stage = "N8G2_gate_policy_review"
    elif gross_degrades:
        status = "fgo_feedback_policy_not_ready"
        next_stage = "N8G2_feedback_covariance_gate_review"
    else:
        status = "fgo_feedback_ekf_foundation_ready"
        next_stage = "N8H_feedback_visual_validation_and_ablation"
    return {
        "stage": "N8G",
        "status": status,
        "recommended_next_stage": next_stage,
        "feedback_observations_generated": feedback_rows,
        "feedback_update_count": total_updates,
        "feedback_accept_count": total_accept,
        "feedback_reject_count": total_reject,
        "gross_degradation_status": evaluation_report.get("gross_degradation_status"),
        "fgo_feedback_output_substitution": False,
        "fgo_feedback_direct_nav_override": False,
        "fgo_feedback_no_future_data": True,
        "no_output_substitution": True,
        "no_direct_nav_overwrite": True,
        "no_trace_finalv23_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_decision_report(path: str | Path, report: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
