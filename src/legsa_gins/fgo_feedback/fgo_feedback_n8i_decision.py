"""N8I feedback ablation decision.

中文说明：决策只基于 solver 可见诊断和 replay 稳定性，不做论文性能宣称。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import safe_int, write_json


def build_n8i_decision_report(
    *,
    policy_grid: dict[str, Any],
    gate_review: dict[str, Any],
    covariance_review: dict[str, Any],
    window_review: dict[str, Any],
    mode_summaries: dict[str, Any],
    mode_comparison: dict[str, Any],
    attitude_spike_review: dict[str, Any],
    figure_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    figures_ok = figure_manifest is None or figure_manifest.get("all_required_figures_nonempty") is True
    variants = mode_summaries.get("variants", [])
    feedback_variants = [item for item in variants if item.get("policy_id") != "baseline_no_feedback"]
    all_degrade = bool(feedback_variants) and all(item.get("gross_degradation") for item in feedback_variants)
    reject_all_ok = mode_summaries.get("reject_all_sanity_passed") is True
    pva = next((item for item in variants if item.get("policy_id") == "diagnostic_PVA"), {})
    selected_gate = gate_review.get("selected_gate_policy", "default_gate")
    selected_covariance = covariance_review.get("selected_covariance_policy", "inflation_auto_from_residual_proxy")
    selected_window = window_review.get("selected_window_policy", "window_5s_stride_1s")
    status, next_stage, selected_policy = _select_status(
        all_degrade=all_degrade,
        reject_all_ok=reject_all_ok,
        figures_ok=figures_ok,
        gate_review=gate_review,
        covariance_policy=selected_covariance,
        variants=variants,
        attitude_spike_review=attitude_spike_review,
    )
    return {
        "stage": "N8I",
        "status": status,
        "recommended_next_stage": next_stage,
        "selected_feedback_policy": selected_policy,
        "selected_gate_policy": selected_gate,
        "selected_covariance_policy": selected_covariance,
        "selected_window_policy": selected_window,
        "selected_feedback_mode": _mode_for_policy(variants, selected_policy),
        "policy_grid_curated_count": policy_grid.get("runtime_curated_policy_count"),
        "figure_count": figure_manifest.get("figure_count_total") if figure_manifest else 0,
        "required_figures_nonempty": figures_ok,
        "reject_all_sanity_passed": reject_all_ok,
        "position_diagnostic_PVA_caveat": _pva_caveat(pva),
        "attitude_spike_review": {
            "default_attitude_spike_count": attitude_spike_review.get("default_attitude_spike_count"),
            "conservative_gate_reject_count_for_attitude_or_yaw": attitude_spike_review.get(
                "conservative_gate_reject_count_for_attitude_or_yaw"
            ),
            "spike_pattern": attitude_spike_review.get("spike_pattern"),
        },
        "mode_comparison_status": mode_comparison.get("gross_degradation_status"),
        "decision_basis": [
            "accepted_rejected_counts",
            "correction_norm_stats",
            "finite_outputs",
            "gross_degradation_screen",
            "no_future_data_feedback",
            "no_output_substitution",
            "solver_visible_diagnostics",
        ],
        "fgo_feedback_output_substitution": False,
        "fgo_feedback_direct_nav_override": False,
        "output_substitution": False,
        "direct_nav_override": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_finalv23_tuning": True,
        "fgo_feedback_no_future_data": True,
        "paper_performance_claim": False,
    }


def _select_status(
    *,
    all_degrade: bool,
    reject_all_ok: bool,
    figures_ok: bool,
    gate_review: dict[str, Any],
    covariance_policy: str,
    variants: list[dict[str, Any]],
    attitude_spike_review: dict[str, Any],
) -> tuple[str, str, str]:
    if not figures_ok:
        return "feedback_policy_not_ready", "N8I2_feedback_policy_debug", "primary_horizontal_velocity_attitude_default"
    if all_degrade:
        return "feedback_policy_not_ready", "N8I2_feedback_policy_debug", "primary_horizontal_velocity_attitude_default"
    if not reject_all_ok:
        return "feedback_policy_not_ready", "N8I2_feedback_policy_debug", "primary_horizontal_velocity_attitude_default"
    if gate_review.get("classification") == "conservative_gate_recommended":
        return "conservative_feedback_gate_ready", "N8J_feedback_final_validation", "primary_hv_att_conservative_gate"
    if covariance_policy not in {"inflation_auto_from_residual_proxy", "none", ""}:
        return "refined_covariance_policy_ready", "N8J_feedback_final_validation", _policy_for_covariance(covariance_policy)
    attitude_only = next((item for item in variants if item.get("policy_id") == "attitude_only"), {})
    velocity_only = next((item for item in variants if item.get("policy_id") == "velocity_only"), {})
    if (
        safe_int(attitude_spike_review.get("default_attitude_spike_count")) > 0
        and safe_int(attitude_only.get("attitude_spike_count_over_4deg")) > 0
        and not velocity_only.get("gross_degradation", True)
    ):
        return "velocity_feedback_only_recommended", "N8I2_attitude_feedback_review", "velocity_only"
    return "default_feedback_policy_ready", "N8J_feedback_final_validation", "primary_horizontal_velocity_attitude_default"


def _policy_for_covariance(policy: str) -> str:
    if policy == "inflation_x4":
        return "primary_hv_att_cov_x4"
    if policy == "block_velocity_x2_attitude_x4":
        return "cov_velocity_x2_attitude_x4"
    return "primary_horizontal_velocity_attitude_default"


def _mode_for_policy(variants: list[dict[str, Any]], policy_id: str) -> str:
    for item in variants:
        if item.get("policy_id") == policy_id:
            return str(item.get("feedback_mode", ""))
    if policy_id == "primary_hv_att_conservative_gate":
        return "horizontal_velocity_attitude_feedback"
    return "horizontal_velocity_attitude_feedback"


def _pva_caveat(pva: dict[str, Any]) -> str:
    if not pva:
        return "PVA diagnostic unavailable; primary position remains disabled"
    if pva.get("gross_degradation"):
        return "PVA diagnostic is unstable; keep position disabled for primary feedback"
    return "PVA remains diagnostic only; primary position feedback stays disabled"


def write_n8i_decision_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
