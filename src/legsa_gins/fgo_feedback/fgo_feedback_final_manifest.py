"""N8J final feedback manifest.

中文说明：manifest 汇总 selected policy、runtime 输出和禁止边界，不提交运行期文件。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_final_runner import N8JFinalRunBundle
from .fgo_feedback_visual_loader import safe_int, write_json


def build_final_feedback_manifest(
    *,
    bundle: N8JFinalRunBundle,
    selected_policy: dict[str, Any],
    figure_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_id = "n8j_selected_conservative_feedback"
    summary = bundle.policy_summaries.get(selected_id, {})
    gate = bundle.gate_reports.get(selected_id, {})
    return {
        "stage": "N8J",
        "selected_policy_name": selected_policy.get("policy_name"),
        "window_duration_s": selected_policy.get("window_duration_s"),
        "stride_s": selected_policy.get("stride_s"),
        "feedback_mode": selected_policy.get("feedback_mode"),
        "feedback_state_blocks": {
            "position": False,
            "horizontal_velocity": True,
            "attitude": True,
        },
        "feedback_observations": safe_int(bundle.observation_reports.get(selected_id, {}).get("feedback_rows")),
        "accepted": safe_int(summary.get("feedback_accept_count")),
        "rejected": safe_int(summary.get("feedback_reject_count")),
        "rejected_reason_stats": gate.get("reject_reasons", {}),
        "position_feedback_enabled": False,
        "output_substitution": False,
        "direct_nav_override": False,
        "no_future_data": gate.get("no_future_data") is not False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "runtime_outputs_generated": bool(summary.get("runtime_outputs_generated")),
        "runtime_outputs": {
            "NAV": bool(summary.get("nav_generated")),
            "STD": bool(summary.get("std_generated")),
            "EVAL_NAV": bool(summary.get("eval_nav_generated")),
            "RUN_MANIFEST": bool(summary.get("run_manifest_generated")),
        },
        "runtime_artifacts_committed": False,
        "figures_generated": figure_manifest.get("all_required_figures_nonempty") if figure_manifest else False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_final_feedback_manifest(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
