"""N7C6 Go2 proprioceptive joint factor decision.

中文说明：decision 只给工程默认策略建议，不做论文性能或 outperform final_v23 claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _delta(comparison: dict[str, Any], key: str, metric: str) -> float | None:
    value = comparison.get("comparisons", {}).get(key, {}).get("delta", {}).get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def _clean_neutral(comparison: dict[str, Any], key: str) -> bool:
    h = _delta(comparison, key, "horizontal_rmse_m")
    yaw = _delta(comparison, key, "yaw_rmse_deg")
    roll = _delta(comparison, key, "roll_rmse_deg")
    pitch = _delta(comparison, key, "pitch_rmse_deg")
    return (h is None or h <= 0.10) and (yaw is None or yaw <= 0.30) and (roll is None or roll <= 0.20) and (pitch is None or pitch <= 0.20)


def make_n7c6_joint_factor_decision(
    *,
    comparison_report: dict[str, Any],
    nis_report: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> dict[str, Any]:
    joint16_neutral = _clean_neutral(comparison_report, "joint_rp1p6_minus_horizontal_only")
    joint1_neutral = _clean_neutral(comparison_report, "joint_rp1deg_minus_horizontal_only")
    variants = nis_report.get("variants", {})
    joint16_nis = variants.get("joint_rp1p6deg_hv1p0", {})
    joint1_nis = variants.get("joint_rp1deg_hv1p0", {})
    joint16_over = bool(joint16_nis.get("overconfidence_flag"))
    joint1_over = bool(joint1_nis.get("overconfidence_flag"))
    joint16_vs_base_h = _delta(comparison_report, "joint_rp1p6_minus_baseline", "horizontal_rmse_m")
    if joint16_vs_base_h is not None and joint16_vs_base_h > 1.0:
        status = "joint_factor_not_ready"
        recommended = "go2_horizontal_velocity_fixed_1p0"
        next_stage = "N7C7_policy_review_or_N8A"
    elif not joint16_neutral and joint16_over:
        status = "horizontal_factor_only_recommended"
        recommended = "go2_horizontal_velocity_fixed_1p0"
        next_stage = "N7C7_policy_review_or_N8A"
    elif joint1_neutral and not joint1_over:
        status = "stronger_go2_proprioceptive_joint_factor_ready"
        recommended = "joint_rp1deg_hv1p0"
        next_stage = "N7C7_or_N8A_after_review"
    elif joint16_neutral and not joint16_over:
        status = "go2_proprioceptive_joint_factor_ready"
        recommended = "joint_rp1p6_hv1p0"
        next_stage = "N7C7_or_N8A_after_review"
    else:
        status = "horizontal_factor_sufficient"
        recommended = "go2_horizontal_velocity_fixed_1p0"
        next_stage = "N7C7_policy_review_or_N8A"
    return {
        "stage": "N7C6_go2_proprioceptive_joint_factor",
        "status": status,
        "recommended_default": recommended,
        "recommended_next_stage": next_stage,
        "joint_rp1p6_clean_neutral": joint16_neutral,
        "joint_rp1_clean_neutral": joint1_neutral,
        "joint_rp1p6_overconfidence": joint16_over,
        "joint_rp1_overconfidence": joint1_over,
        "figure_count": figure_manifest.get("figure_count_total", 0),
        "figures_generated": bool(figure_manifest.get("required_figures_generated")),
        "figures_nonempty": bool(figure_manifest.get("required_figures_nonempty")),
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_not_truth": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def write_n7c6_joint_factor_decision(path: str | Path, decision: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
