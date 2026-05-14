"""N8B smoothness and yaw-smoothness policy review.

中文说明：审查 smoothness/yaw smoothness，不用删除 smoothness 作为最终捷径。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SMOOTHNESS_VARIANTS = [
    "default_active_stack_n8a2",
    "weak_yaw_smoothness",
    "position_velocity_only_smoothness",
    "no_yaw_smoothness_diagnostic",
    "no_smoothness_diagnostic",
]


def _metric(row: dict[str, Any], key: str) -> float:
    return float(row.get(key, 0.0) or 0.0)


def review_smoothness_policy(ablation_summary: dict[str, Any]) -> dict[str, Any]:
    variants = [row for row in ablation_summary.get("variants", []) if row.get("variant") in SMOOTHNESS_VARIANTS]
    by_name = {str(row.get("variant")): row for row in variants}
    default = by_name.get("default_active_stack_n8a2", {})
    weak = by_name.get("weak_yaw_smoothness", {})
    no_yaw = by_name.get("no_yaw_smoothness_diagnostic", {})
    weak_improves = _metric(weak, "yaw_delta_wrapped_rmse_deg") < _metric(default, "yaw_delta_wrapped_rmse_deg")
    weak_no_degradation = not bool(weak.get("gross_degradation", False)) and bool(weak.get("finite_output", False))
    no_yaw_best = False
    if no_yaw:
        no_yaw_best = _metric(no_yaw, "yaw_delta_wrapped_rmse_deg") <= min(
            _metric(row, "yaw_delta_wrapped_rmse_deg") for row in variants
        )
    if weak_improves and weak_no_degradation:
        recommendation = "weak_yaw_smoothness_policy"
    elif no_yaw_best:
        recommendation = "N8C_yaw_smoothing_redesign_not_final_deletion"
    else:
        recommendation = "keep_default_smoothness_until_more_evidence"
    return {
        "stage": "N8B_fgo_factor_graph_policy_review",
        "review_goal": "separate_position_velocity_yaw_smoothness_policy",
        "smoothness_policy_metrics": [
            {
                "variant": row.get("variant"),
                "smoothness_policy": row.get("smoothness_policy"),
                "yaw_delta_wrapped_rmse": row.get("yaw_delta_wrapped_rmse_deg"),
                "horizontal_delta_rmse": row.get("horizontal_delta_rmse_m"),
                "residual_proxy_p95": row.get("residual_proxy_p95"),
                "final_cost": row.get("final_cost"),
                "finite_output": row.get("finite_output"),
                "gross_degradation": row.get("gross_degradation"),
                "smoothness_factor_deleted_for_metric": False,
            }
            for row in variants
        ],
        "weak_yaw_smoothness_improves_without_degradation": bool(weak_improves and weak_no_degradation),
        "no_yaw_smoothness_best_diagnostic": bool(no_yaw_best),
        "recommended_policy": recommendation,
        "secondary_recommendation": "N8B2_yaw_smoothness_redesign" if no_yaw_best else "",
        "smoothness_factor_deleted_for_metric": False,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }


def write_smoothness_policy_review(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
