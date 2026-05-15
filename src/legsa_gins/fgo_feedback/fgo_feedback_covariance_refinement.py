"""N8I feedback covariance refinement review.

中文说明：协方差消融只允许保守放大或 block-wise inflation，不做 R shrink，
不使用 trace/final_v23 调权。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_policy_ablation_runner import N8IPolicyRunBundle, policy_trace_stats
from .fgo_feedback_visual_loader import safe_float, safe_int, write_json


COVARIANCE_POLICY_IDS = [
    "cov_inflation_x1",
    "cov_inflation_x2",
    "cov_inflation_x4",
    "cov_auto_residual_proxy",
    "cov_velocity_x2_attitude_x4",
    "cov_attitude_x6_diagnostic",
]


def build_covariance_refinement_report(bundle: N8IPolicyRunBundle) -> dict[str, Any]:
    entries = [_covariance_entry(bundle, policy_id) for policy_id in COVARIANCE_POLICY_IDS if policy_id in bundle.policy_summaries]
    selected = _select_covariance_policy(entries)
    n8g_cov = bundle.n8g_reports.get("FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json", {})
    return {
        "stage": "N8I",
        "source_stage": "N8H",
        "n8h_covariance_context": {
            "covariance_source": n8g_cov.get("covariance_source", "conservative_residual_proxy"),
            "conservative_inflation_factor": safe_float(n8g_cov.get("conservative_inflation_factor")),
            "std_v_stats": n8g_cov.get("std_v_stats", {}),
            "std_att_stats": n8g_cov.get("std_att_stats", {}),
        },
        "covariance_sweep": entries,
        "selected_covariance_policy": selected,
        "selected_covariance_reason": _selected_reason(selected),
        "no_R_shrink_claim": True,
        "selection_basis": "solver_visible_correction_norm_acceptance_and_gross_degradation",
        "no_trace_tuning": True,
        "no_finalv23_tuning": True,
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _covariance_entry(bundle: N8IPolicyRunBundle, policy_id: str) -> dict[str, Any]:
    summary = bundle.policy_summaries.get(policy_id, {})
    covariance = bundle.covariance_reports.get(policy_id, {})
    evaluation = bundle.evaluation_by_policy.get(policy_id, {})
    trace_stats = policy_trace_stats(bundle, policy_id)
    return {
        "policy_id": policy_id,
        "covariance_policy": summary.get("covariance_policy"),
        "base_inflation": covariance.get("base_inflation"),
        "block_scales": covariance.get("block_scales", {}),
        "std_p_stats": covariance.get("std_p_stats", {}),
        "std_v_stats": covariance.get("std_v_stats", {}),
        "std_att_stats": covariance.get("std_att_stats", {}),
        "runtime_accept_count": safe_int(summary.get("feedback_accept_count")),
        "runtime_reject_count": safe_int(summary.get("feedback_reject_count")),
        "attitude_spike_count_over_4deg": trace_stats["attitude_spike_count_over_4deg"],
        "correction_norm_stats": trace_stats,
        "baseline_delta": evaluation.get("feedback_vs_baseline_delta", {}),
        "gross_degradation": bool(evaluation.get("clean_gross_degradation", False)),
        "finite_output": bool(summary.get("eval_nav_generated")),
        "diagnostic_only": bool(summary.get("diagnostic_only")),
        "no_R_shrink": covariance.get("no_R_shrink") is True,
    }


def _select_covariance_policy(entries: list[dict[str, Any]]) -> str:
    stable = [item for item in entries if item.get("finite_output") and not item.get("gross_degradation")]
    if not stable:
        return "inflation_auto_from_residual_proxy"
    block = next((item for item in stable if item.get("policy_id") == "cov_velocity_x2_attitude_x4"), None)
    auto = next((item for item in stable if item.get("policy_id") == "cov_auto_residual_proxy"), None)
    x4 = next((item for item in stable if item.get("policy_id") == "cov_inflation_x4"), None)
    if block and safe_int(block.get("attitude_spike_count_over_4deg")) <= safe_int((auto or {}).get("attitude_spike_count_over_4deg", 999999)):
        return "block_velocity_x2_attitude_x4"
    if x4 and safe_int(x4.get("attitude_spike_count_over_4deg")) <= safe_int((auto or {}).get("attitude_spike_count_over_4deg", 999999)):
        return "inflation_x4"
    return "inflation_auto_from_residual_proxy"


def _selected_reason(policy_id: str) -> str:
    if policy_id == "block_velocity_x2_attitude_x4":
        return "block-wise conservative inflation keeps primary position disabled and gives extra attitude damping"
    if policy_id == "inflation_x4":
        return "global x4 inflation is a conservative candidate under replay diagnostics"
    return "current residual-proxy inflation remains the conservative baseline"


def write_covariance_refinement_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
