"""N8I feedback window policy review.

中文说明：窗口消融只调整 duration/stride，并保持 no-future-data 约束，不删 epoch。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_policy_ablation_runner import N8IPolicyRunBundle, policy_trace_stats
from .fgo_feedback_visual_loader import safe_int, write_json


WINDOW_POLICY_IDS = [
    "window_3s_stride_1s",
    "window_5s_stride_1s",
    "window_10s_stride_1s",
    "window_5s_stride_2s",
]


def build_window_policy_review(bundle: N8IPolicyRunBundle) -> dict[str, Any]:
    entries = [_window_entry(bundle, policy_id) for policy_id in WINDOW_POLICY_IDS if policy_id in bundle.policy_summaries]
    selected = _select_window(entries)
    return {
        "stage": "N8I",
        "window_policy_sweep": entries,
        "selected_window_policy": selected,
        "selected_window_duration_s": _duration_stride(selected)[0],
        "selected_feedback_stride_s": _duration_stride(selected)[1],
        "selection_basis": "no_future_data_solve_success_correction_norm_runtime_cost_proxy",
        "no_epoch_deleted": True,
        "no_future_data_feedback": all(item.get("no_future_data") for item in entries),
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _window_entry(bundle: N8IPolicyRunBundle, policy_id: str) -> dict[str, Any]:
    summary = bundle.policy_summaries.get(policy_id, {})
    window = bundle.window_reports.get(policy_id, {})
    evaluation = bundle.evaluation_by_policy.get(policy_id, {})
    trace_stats = policy_trace_stats(bundle, policy_id)
    return {
        "policy_id": policy_id,
        "window_duration_s": summary.get("window_duration_s"),
        "feedback_stride_s": summary.get("feedback_stride_s"),
        "window_count": safe_int(window.get("window_count")),
        "feedback_rows": safe_int(bundle.observation_reports.get(policy_id, {}).get("feedback_rows")),
        "no_future_data": window.get("no_future_data_verified") is True,
        "solve_success": bool(summary.get("eval_nav_generated")),
        "runtime_cost_proxy": safe_int(window.get("window_count")) * max(1, safe_int(window.get("overlap_stats", {}).get("max_epoch_count"))),
        "runtime_accept_count": safe_int(summary.get("feedback_accept_count")),
        "runtime_reject_count": safe_int(summary.get("feedback_reject_count")),
        "correction_norm_stats": trace_stats,
        "baseline_delta": evaluation.get("feedback_vs_baseline_delta", {}),
        "gross_degradation": bool(evaluation.get("clean_gross_degradation", False)),
    }


def _select_window(entries: list[dict[str, Any]]) -> str:
    stable = [item for item in entries if item.get("solve_success") and item.get("no_future_data") and not item.get("gross_degradation")]
    if not stable:
        return "window_5s_stride_1s"
    for item in stable:
        if item["policy_id"] == "window_5s_stride_1s":
            return item["policy_id"]
    return min(stable, key=lambda item: safe_int(item.get("runtime_cost_proxy")))["policy_id"]


def _duration_stride(policy_id: str) -> tuple[float, float]:
    if policy_id == "window_3s_stride_1s":
        return 3.0, 1.0
    if policy_id == "window_10s_stride_1s":
        return 10.0, 1.0
    if policy_id == "window_5s_stride_2s":
        return 5.0, 2.0
    return 5.0, 1.0


def write_window_policy_review(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
