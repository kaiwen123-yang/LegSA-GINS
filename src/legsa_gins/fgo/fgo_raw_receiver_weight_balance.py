"""N8D Raw Doppler versus receiver velocity weight balance.

中文说明：Raw Doppler 已进入 solver residual；这里审查它与 receiver velocity 的权重平衡。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_formal_ablation_matrix import run_n8d_weight_policy_variants
from legsa_gins.fgo.fgo_weight_policy_grid import RAW_RECEIVER_BALANCE_VARIANTS


def run_raw_receiver_weight_balance(
    *,
    ekf_rows: list[dict[str, Any]],
    raw_factors: list[Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    variant_report, rows = run_n8d_weight_policy_variants(
        ekf_rows=ekf_rows,
        raw_factors=raw_factors,
        variants=RAW_RECEIVER_BALANCE_VARIANTS,
    )
    report = build_raw_receiver_weight_balance_report(variant_report)
    return report, rows


def build_raw_receiver_weight_balance_report(variant_report: dict[str, Any]) -> dict[str, Any]:
    summaries = list(variant_report.get("variants", []))
    rows = []
    for summary in summaries:
        balance = {row.get("factor_type"): row for row in summary.get("factor_balance", [])}
        rows.append(
            {
                "variant": summary.get("variant"),
                "solve_status": summary.get("solve_status"),
                "finite_output": summary.get("finite_output"),
                "raw_residual_contribution": balance.get("RawDopplerVelocityFactor", {}).get("total_whitened_contribution", 0.0),
                "receiver_residual_contribution": balance.get("ReceiverVelocityFactor", {}).get("total_whitened_contribution", 0.0),
                "raw_doppler_share": summary.get("raw_doppler_contribution_share", 0.0),
                "horizontal_delta_rmse_m": summary.get("horizontal_delta_rmse_m", 0.0),
                "yaw_delta_wrapped_rmse_deg": summary.get("yaw_delta_wrapped_rmse_deg", 0.0),
                "gross_degradation": summary.get("gross_degradation", False),
                "diagnostic_only": summary.get("diagnostic_only", False),
            }
        )
    active = [row for row in rows if not row["diagnostic_only"] and row["finite_output"] and not row["gross_degradation"]]
    best = max(active, key=lambda row: float(row.get("raw_doppler_share", 0.0) or 0.0), default={})
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "variants": rows,
        "required_variants": RAW_RECEIVER_BALANCE_VARIANTS,
        "all_required_variants_run": sorted(RAW_RECEIVER_BALANCE_VARIANTS) == sorted(str(row.get("variant")) for row in rows),
        "best_solver_visible_raw_receiver_balance": best.get("variant"),
        "raw_doppler_remains_low_marginal_value": float(best.get("raw_doppler_share", 0.0) or 0.0) < 0.05,
        "no_paper_claim": True,
        "trace_weight_tuning": False,
        "final_v23_weight_tuning": False,
        "no_feedback": True,
        "output_substitution": False,
    }
