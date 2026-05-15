"""N8J final feedback evaluator.

中文说明：评价只输出 metric namespaces 和 baseline delta，不把 trace/final_v23
评价结果回写 solver。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_final_runner import N8JFinalRunBundle, final_policy_trace_stats
from .fgo_feedback_visual_loader import safe_int, write_json


def build_final_evaluation_report(bundle: N8JFinalRunBundle) -> dict[str, Any]:
    selected_id = "n8j_selected_conservative_feedback"
    selected_eval = bundle.evaluation_by_policy.get(selected_id, {})
    default_eval = bundle.evaluation_by_policy.get("default_gate_feedback_for_reference", {})
    reject_eval = bundle.evaluation_by_policy.get("reject_all_sanity", {})
    selected_summary = bundle.policy_summaries.get(selected_id, {})
    return {
        "stage": "N8J",
        "baseline_variant": "baseline_no_feedback",
        "selected_feedback_variant": selected_id,
        "baseline_no_feedback_evaluation": {"available": True, "role": "baseline_reference"},
        "selected_feedback_evaluation": selected_eval,
        "selected_feedback_minus_baseline_delta": selected_eval.get("feedback_vs_baseline_delta", {}),
        "default_gate_reference": default_eval,
        "reject_all_sanity": reject_eval,
        "feedback_correction_stats": final_policy_trace_stats(bundle, selected_id),
        "feedback_counts": {
            "observations": safe_int(bundle.observation_reports.get(selected_id, {}).get("feedback_rows")),
            "accepted": safe_int(selected_summary.get("feedback_accept_count")),
            "rejected": safe_int(selected_summary.get("feedback_reject_count")),
        },
        "metric_namespaces": [
            "feedback_vs_baseline_delta",
            "feedback_vs_reference_evaluation_only",
            "reject_all_sanity_delta",
            "no_final_v23_solver_input",
            "no_trace_solver_input",
        ],
        "feedback_vs_reference_evaluation_only": {"available": False, "solver_input": False},
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_final_evaluation_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
