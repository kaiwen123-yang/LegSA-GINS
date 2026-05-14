"""N8A2 yaw convention fix decision rules.

中文说明：决策只描述 N8A2 修复状态，不做论文性能 claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n8a2_decision(
    *,
    contract: dict[str, Any],
    regression: dict[str, Any],
    variant_summary: dict[str, Any],
    comparison: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    variants = {row.get("variant"): row for row in variant_summary.get("variants", [])}
    default = variants.get("yaw_wrap_fixed_default_active_stack", {})
    no_smoothness = variants.get("yaw_wrap_fixed_no_smoothness_diagnostic", {})
    default_wrapped = float(default.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)
    no_smooth_wrapped = float(no_smoothness.get("yaw_delta_wrapped_rmse_deg", default_wrapped) or 0.0)
    gross_degradation = bool(comparison.get("gross_degradation", False))
    if not contract.get("dual_yaw_wrap") or not contract.get("smoothness_wrap") or not contract.get("yaw_rate_wrap") or not regression.get("all_tests_passed"):
        status = "yaw_wrap_fix_failed"
        recommended = "N8A3_yaw_residual_debug"
    elif default_wrapped > 10.0:
        status = "yaw_delta_still_large_factor_policy_review_needed"
        recommended = "N8A3_factor_policy_review"
    elif comparison.get("yaw_delta_wrapped_improvement_deg", 0.0) > 1.0 and not gross_degradation:
        status = "yaw_convention_fixed_foundation_ready"
        recommended = "N8B_factor_graph_policy_review"
    else:
        status = "yaw_wrap_fixed_smoothness_policy_caveat"
        recommended = "N8B_smoothness_policy_review"
    secondary = ""
    if default_wrapped > no_smooth_wrapped + 1.0:
        secondary = "N8B_smoothness_weight_review"
    return {
        "stage": "N8A2_fgo_yaw_convention_fix",
        "status": status,
        "recommended_next_stage": recommended,
        "secondary_recommendation": secondary,
        "default_fixed_yaw_delta_wrapped_rmse_deg": default_wrapped,
        "default_fixed_yaw_delta_raw_rmse_deg": default.get("yaw_delta_raw_rmse_deg"),
        "n8a_reference_yaw_delta_wrapped_rmse_deg": comparison.get("n8a_reference_yaw_delta_wrapped_rmse_deg"),
        "yaw_delta_wrapped_improvement_deg": comparison.get("yaw_delta_wrapped_improvement_deg"),
        "residual_cost_after_fix": default.get("final_cost"),
        "figures_generated": figures.get("required_figures_generated", False),
        "figures_nonempty": figures.get("required_figures_nonempty", False),
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_replaces_ekf_nav": False,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_yaw_correction": False,
        "smoothness_factor_deleted": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_n8a2_decision(path: str | Path, decision: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
