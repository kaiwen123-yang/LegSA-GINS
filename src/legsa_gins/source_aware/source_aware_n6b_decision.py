"""N6B source-aware policy refinement decision rules.

中文说明：决策只总结诊断证据，不开放 Go2/FGO 或 paper claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n6b_source_aware_decision(
    weight_stats: dict[str, Any],
    comparison: dict[str, Any],
    spike_response: dict[str, Any],
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    main_stats = weight_stats.get("main_variant_stats", {})
    trace_generated = bool(main_stats.get("source_aware_trace_generated"))
    stats_by_source = main_stats.get("stats_by_source", {})
    any_scale_changed = any((row.get("R_scale_changed_count", 0) or 0) > 0 for row in stats_by_source.values())
    comparisons = comparison.get("comparisons", {})
    clean_label = (comparisons.get("n6b_lsim_oim_minus_no_sourceaware") or {}).get("diagnostic_label")
    clean_gate_pass = bool((diagnostics or {}).get("clean_neutrality_gate", {}).get("pass"))
    stress_labels = [
        row.get("diagnostic_label")
        for key, row in comparisons.items()
        if key.startswith("receiver_velocity_") and isinstance(row, dict)
    ]
    stress_benefit = any(label == "diagnostic_improvement" for label in stress_labels)
    spike_status = spike_response.get("response_status", "evidence_missing")
    spike_ok = spike_status in {"increased_strongly", "increased_mildly"}

    if not trace_generated or not any_scale_changed:
        status = "not_activated"
        next_stage = "N6B2_source_aware_activation_fix"
    elif not clean_gate_pass or clean_label == "diagnostic_degradation":
        status = "needs_policy_fix"
        next_stage = "N6C_source_aware_threshold_review"
    elif clean_gate_pass and stress_benefit and spike_ok:
        status = "ready_for_go2_weak_prior_or_extended_source_weighting"
        next_stage = "N7A_go2_body_state_weak_prior_foundation"
    elif clean_gate_pass and stress_benefit and not spike_ok:
        status = "ready_with_spike_response_caveat"
        next_stage = "N6C_spike_response_policy_review_or_N7A"
    elif clean_gate_pass and not stress_benefit and not spike_ok:
        status = "ready_with_spike_response_caveat"
        next_stage = "N6C_spike_response_policy_review_or_N7A"
    elif clean_gate_pass and not stress_benefit:
        status = "ready_with_weak_stress_evidence"
        next_stage = "N6C_source_aware_stress_policy_review_or_N7A"
    else:
        status = "policy_refined_clean_neutral"
        next_stage = "N6C_source_aware_stress_policy_review_or_N7A"

    return {
        "stage": "N6B_source_aware_policy_refinement",
        "policy_version": "n6b_conservative_innovation_covariance",
        "status": status,
        "recommended_next_stage": next_stage,
        "source_aware_trace_generated": trace_generated,
        "source_aware_R_scale_changed": any_scale_changed,
        "clean_neutrality_gate_pass": clean_gate_pass,
        "clean_diagnostic_label": clean_label,
        "stress_labels": stress_labels,
        "spike_response_status": spike_status,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "output_only_correction": False,
        "trace_tuning": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
        "go2_prior": False,
    }


def write_n6b_decision(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
