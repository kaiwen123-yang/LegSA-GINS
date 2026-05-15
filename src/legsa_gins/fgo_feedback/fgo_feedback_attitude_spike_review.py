"""N8I attitude correction spike review.

中文说明：复核 4 deg 以上 attitude correction spike，判断保守 gate 是否会拦截；
不把评价 trace/final_v23 作为 solver 输入。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_policy_ablation_runner import N8IPolicyRunBundle, policy_trace_stats
from .fgo_feedback_visual_loader import safe_float, safe_int, write_json


def build_attitude_spike_review(bundle: N8IPolicyRunBundle) -> dict[str, Any]:
    default_id = "primary_horizontal_velocity_attitude_default"
    conservative_id = "primary_hv_att_conservative_gate"
    default_stats = policy_trace_stats(bundle, default_id)
    conservative_stats = policy_trace_stats(bundle, conservative_id)
    default_spikes = _spike_epochs(bundle.trace_rows.get(default_id, []))
    conservative_gate = bundle.gate_reports.get(conservative_id, {})
    rejected_by_conservative = safe_int(conservative_gate.get("reject_reasons", {}).get("attitude_correction_gate")) + safe_int(
        conservative_gate.get("reject_reasons", {}).get("yaw_correction_gate")
    )
    top_times = [item["time"] for item in default_spikes[:5]]
    return {
        "stage": "N8I",
        "source_stage": "N8H",
        "default_policy_id": default_id,
        "conservative_policy_id": conservative_id,
        "attitude_spike_threshold_deg": 4.0,
        "default_attitude_spike_count": len(default_spikes),
        "n8h_primary_attitude_spike_count": safe_int(
            bundle.n8h_reports.get("FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json", {}).get("attitude_correction_spike_count_primary")
        ),
        "top_spike_epochs": default_spikes[:10],
        "top_spike_time_segments": _segments(top_times, half_width_s=1.0),
        "conservative_gate_reject_count_for_attitude_or_yaw": rejected_by_conservative,
        "would_conservative_gate_reject_spikes": rejected_by_conservative > 0,
        "default_correction_stats": default_stats,
        "conservative_correction_stats": conservative_stats,
        "associated_fgo_window_residual": {"available": False, "reason": "per-window_residual_series_not_available"},
        "associated_factor_residuals": {"available": False, "reason": "factor_residual_series_not_available"},
        "spike_pattern": "repeated" if len(default_spikes) >= 3 else ("isolated" if default_spikes else "absent"),
        "stability_review": _stability_review(bundle, conservative_id),
        "no_trace_tuning": True,
        "no_finalv23_tuning": True,
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _spike_epochs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spikes = []
    for row in rows:
        attitude = safe_float(row.get("attitude_norm_deg"))
        if attitude <= 4.0:
            continue
        spikes.append(
            {
                "time": safe_float(row.get("update_time", row.get("observation_time"))),
                "attitude_norm_deg": attitude,
                "yaw_residual_deg": safe_float(row.get("yaw_residual_deg")),
                "velocity_norm_mps": safe_float(row.get("velocity_norm_mps")),
                "position_norm_m": safe_float(row.get("position_norm_m")),
                "accepted": safe_int(row.get("accepted")) == 1,
            }
        )
    return sorted(spikes, key=lambda item: item["attitude_norm_deg"], reverse=True)


def _segments(times: list[float], *, half_width_s: float) -> list[dict[str, float]]:
    return [{"start_s": time - half_width_s, "center_s": time, "end_s": time + half_width_s} for time in times]


def _stability_review(bundle: N8IPolicyRunBundle, policy_id: str) -> str:
    evaluation = bundle.evaluation_by_policy.get(policy_id, {})
    if evaluation.get("clean_gross_degradation"):
        return "conservative_gate_replay_has_gross_degradation"
    if safe_int(bundle.policy_summaries.get(policy_id, {}).get("feedback_accept_count")) <= 0:
        return "conservative_gate_rejects_all_feedback"
    return "conservative_gate_replay_stable_by_gross_degradation_screen"


def write_attitude_spike_review(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
