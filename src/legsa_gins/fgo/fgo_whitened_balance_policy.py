"""N8D whitened residual balance policy.

中文说明：只用 solver-visible whitened residual 和 contribution share 审查权重平衡。
"""

from __future__ import annotations

from typing import Any


BALANCE_FACTORS = [
    "SmoothnessFactor",
    "RawDopplerVelocityFactor",
    "ReceiverVelocityFactor",
    "Go2ProprioceptiveJointFactor",
    "DualYawFactor",
]


def _variant_factor_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(summary.get("factor_balance", []))
    return [row for row in rows if row.get("factor_type") in BALANCE_FACTORS]


def build_whitened_balance_policy_report(variant_report: dict[str, Any]) -> dict[str, Any]:
    variants = list(variant_report.get("variants", []))
    policy_rows: list[dict[str, Any]] = []
    recommended: list[str] = []
    for summary in variants:
        factors = _variant_factor_rows(summary)
        shares = {row["factor_type"]: float(row.get("contribution_share", 0.0) or 0.0) for row in factors}
        dims = {row["factor_type"]: float(row.get("dimension_normalized_whitened_norm", 0.0) or 0.0) for row in factors}
        smooth_share = shares.get("SmoothnessFactor", 0.0)
        raw_share = shares.get("RawDopplerVelocityFactor", 0.0)
        finite = bool(summary.get("finite_output")) and not bool(summary.get("gross_degradation"))
        balance_ok = finite and smooth_share < 0.85 and raw_share > 0.0
        if balance_ok and not summary.get("diagnostic_only"):
            recommended.append(str(summary.get("variant")))
        policy_rows.append(
            {
                "variant": summary.get("variant"),
                "policy_family": summary.get("policy_family"),
                "finite_output": summary.get("finite_output"),
                "gross_degradation": summary.get("gross_degradation", False),
                "factor_count": {row["factor_type"]: row.get("factor_count", 0) for row in factors},
                "whitened_residual_p95": {row["factor_type"]: row.get("whitened_residual_p95", 0.0) for row in factors},
                "dimension_normalized_whitened_norm": dims,
                "contribution_share": shares,
                "smoothness_over_dominant": smooth_share >= 0.85,
                "raw_doppler_underweighted": raw_share <= 0.01,
                "balance_ok": balance_ok,
            }
        )
    selected = recommended[:3]
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "policy_rows": policy_rows,
        "recommended_candidates": {
            "balanced_policy_A": "balanced_policy_A" if "balanced_policy_A" in recommended else (selected[0] if selected else ""),
            "balanced_policy_B": "balanced_policy_B" if "balanced_policy_B" in recommended else (selected[1] if len(selected) > 1 else ""),
            "conservative_policy": "conservative_policy" if "conservative_policy" in recommended else (selected[2] if len(selected) > 2 else ""),
            "aggressive_diagnostic_policy": "no_smoothness_diagnostic",
        },
        "over_dominant_smoothness_variants": [row["variant"] for row in policy_rows if row["smoothness_over_dominant"]],
        "underweighted_raw_doppler_variants": [row["variant"] for row in policy_rows if row["raw_doppler_underweighted"]],
        "smoothness_dominance_detected": any(row["smoothness_over_dominant"] for row in policy_rows),
        "raw_doppler_low_marginal_value_suspect": any(row["raw_doppler_underweighted"] for row in policy_rows),
        "selection_uses_solver_visible_diagnostics_only": True,
        "trace_weight_tuning": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "no_feedback": True,
        "output_substitution": False,
    }
