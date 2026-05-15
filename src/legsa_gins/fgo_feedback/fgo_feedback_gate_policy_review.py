"""N8I feedback gate policy review.

中文说明：gate 消融只看 solver 可见 correction/gate 统计，不用 trace/final_v23
调门限。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_policy_ablation_runner import N8IPolicyRunBundle, policy_trace_stats
from .fgo_feedback_visual_loader import safe_float, safe_int, write_json


GATE_POLICY_IDS = [
    "gate_default_primary",
    "gate_attitude_max_4deg",
    "gate_attitude_max_3deg",
    "gate_combined_conservative",
]


def build_gate_policy_review(bundle: N8IPolicyRunBundle) -> dict[str, Any]:
    entries = [_gate_entry(bundle, policy_id) for policy_id in GATE_POLICY_IDS if policy_id in bundle.policy_summaries]
    default = next((item for item in entries if item["policy_id"] == "gate_default_primary"), {})
    conservative = next((item for item in entries if item["policy_id"] == "gate_combined_conservative"), {})
    n8h_correction = bundle.n8h_reports.get("FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json", {})
    n8h_spikes = safe_int(n8h_correction.get("attitude_correction_spike_count_primary"))
    selected_gate, classification = _classify(default, conservative, n8h_spikes)
    return {
        "stage": "N8I",
        "source_stage": "N8H",
        "n8h_gate_review": {
            "accepted": safe_int(bundle.n8g_reports.get("FGO_FEEDBACK_GATE_REPORT.json", {}).get("accept_count")),
            "rejected": safe_int(bundle.n8g_reports.get("FGO_FEEDBACK_GATE_REPORT.json", {}).get("reject_count")),
            "attitude_p95_deg": safe_float(
                bundle.n8g_reports.get("FGO_FEEDBACK_GATE_REPORT.json", {})
                .get("correction_norm_stats", {})
                .get("attitude_deg", {})
                .get("p95")
            ),
            "attitude_max_deg": safe_float(
                bundle.n8g_reports.get("FGO_FEEDBACK_GATE_REPORT.json", {})
                .get("correction_norm_stats", {})
                .get("attitude_deg", {})
                .get("max")
            ),
            "attitude_spike_count_over_4deg": n8h_spikes,
        },
        "gate_sweep": entries,
        "classification": classification,
        "selected_gate_policy": selected_gate,
        "selected_gate_reason": _selected_reason(classification),
        "conservative_gate_reduces_spike_candidates": bool(
            conservative and safe_int(conservative.get("pre_runtime_reject_count")) > 0 and n8h_spikes > 0
        ),
        "selection_basis": "solver_visible_correction_norm_and_replay_stability",
        "no_trace_tuning": True,
        "no_finalv23_tuning": True,
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _gate_entry(bundle: N8IPolicyRunBundle, policy_id: str) -> dict[str, Any]:
    summary = bundle.policy_summaries.get(policy_id, {})
    gate = bundle.gate_reports.get(policy_id, {})
    evaluation = bundle.evaluation_by_policy.get(policy_id, {})
    trace_stats = policy_trace_stats(bundle, policy_id)
    return {
        "policy_id": policy_id,
        "gate_policy": summary.get("gate_policy"),
        "thresholds": gate.get("gate_thresholds", {}),
        "feedback_count": safe_int(gate.get("feedback_count")),
        "pre_runtime_accept_count": safe_int(gate.get("accept_count")),
        "pre_runtime_reject_count": safe_int(gate.get("reject_count")),
        "runtime_accept_count": safe_int(summary.get("feedback_accept_count")),
        "runtime_reject_count": safe_int(summary.get("feedback_reject_count")),
        "reject_reasons": gate.get("reject_reasons", {}),
        "correction_norm_stats": trace_stats,
        "baseline_delta": evaluation.get("feedback_vs_baseline_delta", {}),
        "gross_degradation": bool(evaluation.get("clean_gross_degradation", False)),
        "finite_output": bool(summary.get("eval_nav_generated")),
        "no_output_substitution": summary.get("no_output_substitution") is True,
        "no_direct_nav_override": summary.get("no_direct_nav_override") is True,
    }


def _classify(default: dict[str, Any], conservative: dict[str, Any], n8h_spikes: int) -> tuple[str, str]:
    if not default:
        return "default_gate", "gate_too_strict"
    default_feedback = safe_int(default.get("feedback_count"))
    default_accept = safe_int(default.get("pre_runtime_accept_count"))
    conservative_reject = safe_int(conservative.get("pre_runtime_reject_count")) if conservative else 0
    conservative_degrades = bool(conservative.get("gross_degradation")) if conservative else True
    if conservative and conservative_reject > max(20, default_feedback // 2):
        return "default_gate", "gate_too_strict"
    if default_feedback > 0 and default_accept == default_feedback and n8h_spikes > 0:
        if conservative and conservative_reject > 0 and not conservative_degrades:
            return "combined_conservative_gate", "conservative_gate_recommended"
        return "attitude_max_4deg", "gate_too_loose_needs_tightening"
    return "default_gate", "gate_current_reasonable"


def _selected_reason(classification: str) -> str:
    if classification == "conservative_gate_recommended":
        return "conservative gate rejects large attitude correction candidates without gross degradation"
    if classification == "gate_too_loose_needs_tightening":
        return "default gate accepts all while attitude correction spikes are present"
    if classification == "gate_too_strict":
        return "conservative gate rejects too many feedback candidates"
    return "default gate remains stable under N8I replay diagnostics"


def write_gate_policy_review(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
