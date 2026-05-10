"""N5D1 visual data coverage and spike-audit decision rules.

中文说明：N5D1 只决定 visual validation 是否修复完成；推荐 N6A 只是下一阶段
准入结论，不实现 LSIM/OIM、Go2 prior、source-aware weighting 或 FGO。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n5d1_decision(
    *,
    coverage_report: dict[str, Any],
    spike_report: dict[str, Any],
    semantics_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocking: list[str] = []
    if not coverage_report.get("mandatory_coverage_passed", False):
        blocking.append("mandatory_clean_or_required_figures_empty")
        status = "visual_validation_not_ready"
        next_stage = "N5D2_clean_ablation_timeseries_recovery"
    elif not spike_report or spike_report.get("spike_count") is None:
        blocking.append("spike_audit_missing")
        status = "visual_validation_partial_spike_evidence_missing"
        next_stage = "N5D2_raw_doppler_spike_trace_recovery"
    elif spike_report.get("recommended_action") in {"gating_needed", "provider_quality_issue", "time_alignment_issue"}:
        blocking.append("spike_policy_needed")
        status = "visual_repaired_but_spike_policy_needed"
        if spike_report.get("spike_impact_on_EKF") == "high":
            next_stage = "N5E_raw_doppler_gating_if_high_impact"
        else:
            next_stage = "N6A_source_aware_LSIM_OIM_weighting_foundation_with_spike_caveat"
    else:
        status = "visual_validation_repaired_ready"
        next_stage = "N6A_source_aware_LSIM_OIM_weighting_foundation"
    if semantics_report and not semantics_report.get("velocity_3sigma_semantics_fixed", False):
        blocking.append("plot_semantics_fix_missing")
        if status == "visual_validation_repaired_ready":
            status = "visual_validation_not_ready"
            next_stage = "N5D2_plot_semantics_repair"
    return {
        "stage": "N5D1_visual_data_coverage_spike_audit",
        "status": status,
        "recommended_next_stage": next_stage,
        "blocking_issues": blocking,
        "required_figures_nonempty": coverage_report.get("required_figures_nonempty", False),
        "required_figures_generated": coverage_report.get("required_figures_generated", False),
        "mandatory_coverage_passed": coverage_report.get("mandatory_coverage_passed", False),
        "spike_count": spike_report.get("spike_count"),
        "spike_impact_on_EKF": spike_report.get("spike_impact_on_EKF"),
        "spike_recommended_action": spike_report.get("recommended_action"),
        "velocity_3sigma_semantics_fixed": bool((semantics_report or {}).get("velocity_3sigma_semantics_fixed", False)),
        "duplicate_stress_pair_count": (semantics_report or {}).get("duplicate_stress_pair_count", 0),
        "unique_stress_pair_count": (semantics_report or {}).get("unique_stress_pair_count", 0),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "epoch_deletion": False,
        "gate_tuned": False,
        "source_aware_weighting_implemented": False,
        "lsim_oim_implemented": False,
        "go2_prior_implemented": False,
        "fgo_implemented": False,
    }


def write_n5d1_decision(path: str | Path, decision: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
