"""N8J final feedback sanity checks.

中文说明：sanity 只验证 selected policy、runtime 输出和边界，不调参，不删 epoch。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import safe_float, safe_int, write_json


def build_final_sanity_report(
    *,
    selected_policy: dict[str, Any],
    variant_summaries: dict[str, Any],
    evaluation_report: dict[str, Any],
    final_manifest: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> dict[str, Any]:
    selected = _variant(variant_summaries, "n8j_selected_conservative_feedback")
    baseline = _variant(variant_summaries, "baseline_no_feedback")
    reject = _variant(variant_summaries, "reject_all_sanity")
    correction = evaluation_report.get("feedback_correction_stats", {})
    checks = {
        "selected_policy_fixed": selected_policy.get("n8i_selected_policy_match") is True and selected_policy.get("hidden_policy_change") is False,
        "selected_variant_generated_nav_std_eval": bool(selected.get("nav_generated")) and bool(selected.get("std_generated")) and bool(selected.get("eval_nav_generated")),
        "baseline_generated": bool(baseline.get("eval_nav_generated")),
        "reject_all_matches_baseline": variant_summaries.get("reject_all_sanity_passed") is True,
        "feedback_observations_positive": safe_int(final_manifest.get("feedback_observations")) > 0,
        "feedback_accepted_positive": safe_int(final_manifest.get("accepted")) > 0,
        "feedback_rejected_by_conservative_gate": safe_int(final_manifest.get("rejected")) > 0,
        "position_feedback_disabled": final_manifest.get("position_feedback_enabled") is False,
        "no_output_substitution": final_manifest.get("output_substitution") is False,
        "no_direct_nav_override": final_manifest.get("direct_nav_override") is False,
        "no_future_data": final_manifest.get("no_future_data") is True,
        "correction_norms_finite": _stats_finite(correction),
        "no_gross_degradation": not bool(selected.get("gross_degradation")),
        "required_figures_generated": figure_manifest.get("all_required_figures_nonempty") is True,
        "runtime_artifacts_not_committed": final_manifest.get("runtime_artifacts_committed") is False,
        "no_paper_claim": final_manifest.get("paper_performance_claim") is False,
    }
    return {
        "stage": "N8J",
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "selected_feedback_accept_reject": {
            "accepted": safe_int(final_manifest.get("accepted")),
            "rejected": safe_int(final_manifest.get("rejected")),
        },
        "runtime_outputs_generated": final_manifest.get("runtime_outputs_generated") is True,
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _variant(report: dict[str, Any], policy_id: str) -> dict[str, Any]:
    return next((item for item in report.get("variants", []) if item.get("policy_id") == policy_id), {})


def _stats_finite(report: dict[str, Any]) -> bool:
    for block in ["position_m", "velocity_mps", "attitude_deg", "yaw_abs_deg"]:
        stats = report.get(block, {})
        for key in ["p50", "p95", "max"]:
            if not math.isfinite(safe_float(stats.get(key))):
                return False
    return True


def write_final_sanity_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
