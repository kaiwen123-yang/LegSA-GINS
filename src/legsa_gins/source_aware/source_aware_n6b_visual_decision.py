"""Decision rules for N6B1 source-aware visual validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n6b1_visual_decision(
    *,
    coverage_report: dict[str, Any],
    sanity_report: dict[str, Any],
) -> dict[str, Any]:
    """Map N6B1 visual evidence to a bounded next-stage decision.

    中文说明：这里只给阶段建议，不把图像结论写回 solver，也不形成 paper claim。
    """

    if not coverage_report.get("required_figures_nonempty", False):
        status = "visual_validation_failed_empty_figures"
        next_stage = "N6B2_visual_timeseries_recovery"
    elif not sanity_report.get("receiver_position_not_slammed_to_cap", False) or not sanity_report.get("receiver_velocity_not_slammed_to_cap", False):
        status = "visual_validation_failed_weight_policy"
        next_stage = "N6C_source_aware_threshold_review"
    elif not sanity_report.get("clean_no_gross_degradation_visual", False):
        status = "visual_validation_failed_clean_degradation"
        next_stage = "N6C_source_aware_threshold_review"
    elif not sanity_report.get("raw_doppler_spike_response_visible", False):
        status = "visual_validation_passed_with_spike_response_caveat"
        next_stage = "N7A_or_N7B_after_manual_review"
    elif sanity_report.get("visual_sanity_passed", False) and coverage_report.get("visual_validation_passed", False):
        status = "visual_validation_passed"
        next_stage = "N7A_go2_body_state_weak_prior_or_continue_open_PR32_review"
    else:
        status = "visual_validation_failed_empty_figures"
        next_stage = "N6B2_visual_timeseries_recovery"
    return {
        "stage": "N6B1_source_aware_visual_validation",
        "status": status,
        "recommended_next_stage": next_stage,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_prior": False,
        "fgo": False,
    }


def write_n6b1_visual_decision(path: str | Path, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
