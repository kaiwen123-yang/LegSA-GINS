"""N8D DualYawFactor weight policy review.

中文说明：检查 dual yaw 与 yaw smoothness 的平衡，不用 trace/final_v23 调 yaw 权重。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_formal_ablation_matrix import run_n8d_weight_policy_variants
from legsa_gins.fgo.fgo_weight_policy_grid import DUAL_YAW_VARIANTS


def run_dual_yaw_weight_policy(
    *,
    ekf_rows: list[dict[str, Any]],
    raw_factors: list[Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    variant_report, rows_by_variant = run_n8d_weight_policy_variants(
        ekf_rows=ekf_rows,
        raw_factors=raw_factors,
        variants=DUAL_YAW_VARIANTS,
    )
    return build_dual_yaw_weight_policy_report(variant_report), rows_by_variant


def build_dual_yaw_weight_policy_report(variant_report: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for summary in variant_report.get("variants", []):
        yaw = next((row for row in summary.get("factor_balance", []) if row.get("factor_type") == "DualYawFactor"), {})
        rows.append(
            {
                "variant": summary.get("variant"),
                "finite_output": summary.get("finite_output"),
                "dual_yaw_scale": summary.get("dual_yaw_scale"),
                "yaw_smoothness_scale": summary.get("yaw_smoothness_scale"),
                "dual_yaw_contribution_share": yaw.get("contribution_share", 0.0),
                "yaw_delta_wrapped_rmse_deg": summary.get("yaw_delta_wrapped_rmse_deg", 0.0),
                "gross_degradation": summary.get("gross_degradation", False),
                "diagnostic_only": summary.get("diagnostic_only", False),
            }
        )
    stable = [row for row in rows if row["finite_output"] and not row["gross_degradation"] and not row["diagnostic_only"]]
    best = max(stable, key=lambda row: float(row.get("dual_yaw_contribution_share", 0.0) or 0.0), default={})
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "variants": rows,
        "best_solver_visible_dual_yaw_policy": best.get("variant"),
        "stronger_dual_yaw_with_weak_smoothness_stable": bool(best),
        "yaw_smoothness_not_used_as_trace_tuned_shortcut": True,
        "trace_weight_tuning": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "no_feedback": True,
        "output_substitution": False,
    }
