"""N8D Go2 joint factor weight policy review.

中文说明：Go2 joint 因子只做弱约束工程审查，不宣称 Go2 truth。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_formal_ablation_matrix import run_n8d_weight_policy_variants
from legsa_gins.fgo.fgo_weight_policy_grid import GO2_JOINT_VARIANTS


def run_go2_joint_weight_policy(
    *,
    ekf_rows: list[dict[str, Any]],
    raw_factors: list[Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    variant_report, rows_by_variant = run_n8d_weight_policy_variants(
        ekf_rows=ekf_rows,
        raw_factors=raw_factors,
        variants=GO2_JOINT_VARIANTS,
    )
    return build_go2_joint_weight_policy_report(variant_report), rows_by_variant


def build_go2_joint_weight_policy_report(variant_report: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for summary in variant_report.get("variants", []):
        go2 = next((row for row in summary.get("factor_balance", []) if row.get("factor_type") == "Go2ProprioceptiveJointFactor"), {})
        rows.append(
            {
                "variant": summary.get("variant"),
                "finite_output": summary.get("finite_output"),
                "go2_joint_scale": summary.get("go2_joint_scale"),
                "go2_contribution_share": go2.get("contribution_share", 0.0),
                "go2_dimension_normalized_whitened_norm": go2.get("dimension_normalized_whitened_norm", 0.0),
                "horizontal_delta_rmse_m": summary.get("horizontal_delta_rmse_m", 0.0),
                "yaw_delta_wrapped_rmse_deg": summary.get("yaw_delta_wrapped_rmse_deg", 0.0),
                "roll_delta_rmse_deg": summary.get("roll_delta_rmse_deg", 0.0),
                "pitch_delta_rmse_deg": summary.get("pitch_delta_rmse_deg", 0.0),
                "overconstraint_risk": bool(summary.get("gross_degradation", False)),
                "diagnostic_only": summary.get("diagnostic_only", False),
            }
        )
    stable = [row for row in rows if row["finite_output"] and not row["overconstraint_risk"] and not row["diagnostic_only"]]
    best = max(stable, key=lambda row: float(row.get("go2_contribution_share", 0.0) or 0.0), default={})
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "variants": rows,
        "best_solver_visible_go2_joint_policy": best.get("variant"),
        "go2_joint_stable_low_marginal_value": float(best.get("go2_contribution_share", 0.0) or 0.0) < 0.1,
        "no_go2_truth_claim": True,
        "trace_weight_tuning": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "no_feedback": True,
        "output_substitution": False,
    }
