"""N5D raw Doppler visual/stress decision logic.

中文说明：N5D 只判断 raw Doppler 是否具备进入下一阶段 source-aware weighting
基础工作的资格；不实现 LSIM/OIM、Go2 prior 或 FGO，也不做 paper claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _is_clean_degraded(stress_eval: dict[str, Any], visual_sanity: dict[str, Any]) -> bool:
    if visual_sanity.get("clean_variant_no_gross_divergence") is False:
        return True
    return stress_eval.get("clean_raw_doppler_effect") == "degrades"


def make_n5d_decision(visual_sanity: dict[str, Any], stress_eval: dict[str, Any]) -> dict[str, Any]:
    source_issue = (
        visual_sanity.get("raw_velocity_not_pvt_copy") is False
        or visual_sanity.get("raw_velocity_not_gnss_15col_copy") is False
        or visual_sanity.get("time_alignment_ok") is False
    )
    if source_issue:
        status = "not_ready_source_or_alignment_issue"
        next_stage = "N5E_source_or_time_alignment_fix"
    elif _is_clean_degraded(stress_eval, visual_sanity):
        status = "not_ready_clean_degradation"
        next_stage = "N5E_noise_or_gating_fix"
    elif stress_eval.get("stress_degrade_pair_count", 0) >= 3:
        status = "needs_noise_model_before_next_factor"
        next_stage = "N5E_raw_doppler_noise_gating_fix"
    elif stress_eval.get("stress_help_pair_count", 0) >= 2:
        status = "ready_for_source_aware_weighting"
        next_stage = "N6A_source_aware_LSIM_OIM_weighting_foundation"
    elif stress_eval.get("stress_help_pair_count", 0) >= 1 or stress_eval.get("evidence_raw_doppler_independent_velocity_constraint"):
        status = "ready_with_weak_stress_evidence"
        next_stage = "N6A_source_aware_weighting_with_raw_doppler_as_candidate_source"
    else:
        status = "needs_noise_model_before_next_factor"
        next_stage = "N5E_raw_doppler_noise_gating_fix"

    return {
        "stage": "N5D_raw_doppler_visual_validation_and_velocity_stress_protocol",
        "status": status,
        "recommended_next_stage": next_stage,
        "visual_stress_candidate_passed": bool(visual_sanity.get("visual_stress_candidate_passed", False)),
        "stress_help_pair_count": int(stress_eval.get("stress_help_pair_count", 0) or 0),
        "stress_degrade_pair_count": int(stress_eval.get("stress_degrade_pair_count", 0) or 0),
        "evidence_raw_doppler_independent_velocity_constraint": bool(
            stress_eval.get("evidence_raw_doppler_independent_velocity_constraint", False)
        ),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "tuning_claim": False,
        "epoch_deleted_for_metric": False,
        "lsim_oim_implemented": False,
        "go2_prior_implemented": False,
        "fgo_implemented": False,
    }


def write_decision(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
