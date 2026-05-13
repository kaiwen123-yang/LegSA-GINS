"""Decision rules for N7C3 bounded adaptive Go2 horizontal velocity std.

中文说明：本模块只生成 N7C3 决策报告，不做论文性能声明。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _manifest_int(manifest: dict[str, Any], *keys: str) -> int:
    for key in keys:
        try:
            value = int(manifest.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0
        if value:
            return value
    return 0


def _delta(report: dict[str, Any], name: str, metric: str) -> float | None:
    value = report.get("comparisons", {}).get(name, {}).get("delta", {}).get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def make_n7c3_decision(
    *,
    std_report: dict[str, Any],
    soft_gating_report: dict[str, Any],
    comparison_report: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> dict[str, Any]:
    manifest = comparison_report.get("bounded_adaptive_manifest", {})
    update_count = _manifest_int(
        manifest,
        "go2_horizontal_velocity_prior_update_count",
        "go2_velocity_prior_update_count",
    ) or int(soft_gating_report.get("update_count_expected", 0) or 0)
    skip_count = _manifest_int(manifest, "go2_horizontal_velocity_prior_skip_count") or int(soft_gating_report.get("skip_count", 0) or 0)
    clean_delta = _delta(comparison_report, "bounded_adaptive_minus_fixed_clean", "horizontal_rmse_m")
    receiver_stress_delta = _delta(comparison_report, "receiver_velocity_stress_bounded_adaptive_minus_fixed", "horizontal_rmse_m")
    raw_stress_delta = _delta(comparison_report, "raw_doppler_stress_bounded_adaptive_minus_fixed", "horizontal_rmse_m")
    max_std = max(float(std_report.get("std_vn_max", 0.0) or 0.0), float(std_report.get("std_ve_max", 0.0) or 0.0))
    clean_degrades = clean_delta is not None and clean_delta > 0.10
    stress_values = [value for value in [receiver_stress_delta, raw_stress_delta] if value is not None]
    stress_neutral_or_improved = bool(stress_values) and all(value <= 0.10 for value in stress_values)
    stress_improved = any(value < -0.10 for value in stress_values)
    if max_std > 5.0 or not std_report.get("max_std_le_5", False):
        status = "policy_failed_physical_bound"
        next_stage = "N7C3_repair_std_bounds"
    elif update_count == 0:
        status = "adaptive_activation_failed"
        next_stage = "N7C3_activation_debug"
    elif clean_degrades:
        status = "adaptive_policy_not_ready"
        next_stage = "N7C3_policy_repair"
    elif stress_neutral_or_improved and stress_improved:
        status = "bounded_adaptive_policy_ready_for_N8A"
        next_stage = "merge_PR_38_tag_N7C_then_start_N8A"
    elif stress_neutral_or_improved:
        status = "fixed_std_policy_sufficient_bounded_adaptive_optional"
        next_stage = "merge_PR_38_tag_N7C_then_start_N8A"
    else:
        status = "fixed_std_policy_sufficient_bounded_adaptive_optional"
        next_stage = "merge_PR_38_tag_N7C_then_start_N8A"
    return {
        "stage": "N7C3_go2_horizontal_velocity_bounded_adaptive_std",
        "status": status,
        "recommended_next_stage": next_stage,
        "max_std": max_std,
        "max_std_le_5": max_std <= 5.0 and bool(std_report.get("max_std_le_5", False)),
        "update_count": update_count,
        "skip_count": skip_count,
        "soft_gated_count": int(soft_gating_report.get("soft_gated_count", 0) or 0),
        "clean_bounded_adaptive_minus_fixed_horizontal_rmse_delta_m": clean_delta,
        "receiver_stress_bounded_adaptive_minus_fixed_horizontal_rmse_delta_m": receiver_stress_delta,
        "raw_doppler_stress_bounded_adaptive_minus_fixed_horizontal_rmse_delta_m": raw_stress_delta,
        "readability_figures_generated": bool(figure_manifest.get("required_figures_generated", False)),
        "readability_figures_nonempty": bool(figure_manifest.get("required_figures_nonempty", False)),
        "std_vn_p50": std_report.get("std_vn_p50"),
        "std_vn_p95": std_report.get("std_vn_p95"),
        "std_vn_max": std_report.get("std_vn_max"),
        "std_ve_p50": std_report.get("std_ve_p50"),
        "std_ve_p95": std_report.get("std_ve_p95"),
        "std_ve_max": std_report.get("std_ve_max"),
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_vertical_velocity_prior_enabled": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "vertical_disabled": True,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }


def write_n7c3_decision(path: str | Path, decision: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
