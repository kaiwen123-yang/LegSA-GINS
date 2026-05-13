"""Decision rules for N7C1 visual validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7c1_visual_decision(
    *,
    coverage_report: dict[str, Any],
    sanity_report: dict[str, Any],
    n7c_decision_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map N7C1 figure evidence to a bounded next-stage recommendation.

    中文说明：这里只给 visual gate 决策，不进入 N8A 实现，不把 Go2 velocity 当
    truth，也不形成 paper performance claim。
    """

    n7c_decision = n7c_decision_report or {}
    if not coverage_report.get("required_figures_nonempty", False):
        status = "visual_validation_failed_empty_figures"
        next_stage = "N7C2_timeseries_recovery"
    elif not sanity_report.get("vertical_velocity_disabled_confirmed", False):
        status = "visual_validation_failed_vertical_boundary"
        next_stage = "N7C2_vertical_boundary_fix"
    elif not sanity_report.get("clean_no_gross_degradation_visual", False):
        status = "visual_validation_failed_clean_degradation"
        next_stage = "N7C2_go2_horizontal_policy_review"
    elif not sanity_report.get("stress_variants_visual_stable", False):
        status = "visual_validation_failed_stress_instability"
        next_stage = "N7C2_stress_policy_review"
    elif sanity_report.get("visual_sanity_passed", False) and n7c_decision.get("status") == "ready_with_weak_stress_evidence":
        status = "visual_validation_passed_with_weak_stress_evidence"
        next_stage = "N8A_no_feedback_FGO_foundation"
    elif sanity_report.get("visual_sanity_passed", False):
        status = "visual_validation_passed"
        next_stage = "N8A_no_feedback_FGO_foundation"
    else:
        status = "visual_validation_failed_empty_figures"
        next_stage = "N7C2_timeseries_recovery"
    return {
        "stage": "N7C1_go2_horizontal_velocity_visual_validation",
        "status": status,
        "recommended_next_stage": next_stage,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "epoch_deletion": False,
        "go2_vertical_velocity_prior_enabled": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def write_n7c1_visual_decision(path: str | Path, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
