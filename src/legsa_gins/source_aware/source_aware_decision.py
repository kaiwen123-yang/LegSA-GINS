"""N6A source-aware decision rules.

中文说明：决策只总结诊断工程证据；不做 paper performance claim，不声称超过
final_v23，不开放 Go2 prior/FGO。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_source_aware_decision(
    weight_stats: dict[str, Any],
    comparison: dict[str, Any],
    spike_response: dict[str, Any],
) -> dict[str, Any]:
    main_stats = weight_stats.get("main_variant_stats", {})
    trace_generated = bool(main_stats.get("source_aware_trace_generated"))
    stats_by_source = main_stats.get("stats_by_source", {})
    any_scale_changed = any((row.get("R_scale_changed_count", 0) or 0) > 0 for row in stats_by_source.values())
    comparisons = comparison.get("comparisons", {})
    clean_label = (comparisons.get("baseline_plus_raw_lsim_oim_minus_no_sourceaware") or {}).get("diagnostic_label")
    stress_labels = [
        row.get("diagnostic_label")
        for key, row in comparisons.items()
        if key.startswith("receiver_velocity_") and isinstance(row, dict)
    ]
    stress_benefit = any(label == "diagnostic_improvement" for label in stress_labels)
    stress_degraded = any(label == "diagnostic_degradation" for label in stress_labels)
    spike_ok = bool(spike_response.get("raw_doppler_R_scale_increased_near_spikes"))

    if not trace_generated or not any_scale_changed:
        status = "not_activated"
        next_stage = "N6A2_source_aware_activation_fix"
    elif clean_label == "diagnostic_degradation":
        status = "needs_policy_fix"
        next_stage = "N6B_source_aware_policy_refinement"
    elif clean_label in {"diagnostic_neutral", "diagnostic_improvement"} and stress_benefit and spike_ok:
        status = "ready_for_go2_weak_prior_or_extended_source_weighting"
        next_stage = "N7A_go2_body_state_weak_prior_foundation"
    elif clean_label in {"diagnostic_neutral", "diagnostic_improvement"} and stress_benefit and not spike_ok:
        status = "ready_with_spike_response_caveat"
        next_stage = "N6B_source_aware_spike_response_refinement_or_N7A"
    elif clean_label in {"diagnostic_neutral", "diagnostic_improvement"} and not stress_benefit:
        status = "ready_with_weak_stress_evidence"
        next_stage = "N6B_source_aware_policy_refinement_or_N7A"
    elif stress_degraded:
        status = "needs_lsim_oim_threshold_review"
        next_stage = "N6B_source_aware_threshold_review"
    else:
        status = "needs_lsim_oim_threshold_review"
        next_stage = "N6B_source_aware_threshold_review"

    return {
        "stage": "N6A_source_aware_LSIM_OIM_weighting",
        "status": status,
        "recommended_next_stage": next_stage,
        "source_aware_trace_generated": trace_generated,
        "source_aware_R_scale_changed": any_scale_changed,
        "clean_diagnostic_label": clean_label,
        "stress_labels": stress_labels,
        "spike_response_status": spike_response.get("oim_response_status"),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "output_only_correction": False,
        "trace_tuning": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
        "go2_prior": False,
    }


def write_decision(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
