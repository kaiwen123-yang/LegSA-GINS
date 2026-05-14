"""N8C2 residual whitening and dimension-normalized contribution review.

中文说明：白化审查只用于诊断贡献尺度，不使用 trace/final_v23 调权。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_factor_activation_audit import write_json_report


def _factor_rows(activation_report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(activation_report.get("factor_activation_rows", []))


def build_residual_whitening_review(*, activation_report: dict[str, Any]) -> dict[str, Any]:
    rows = _factor_rows(activation_report)
    total = sum(float(row.get("total_whitened_sq", 0.0) or 0.0) for row in rows)
    review_rows = []
    for row in rows:
        count = int(row.get("residual_row_count", 0) or 0)
        dimension = int(row.get("residual_dimension", 1) or 1)
        whitened_sq = float(row.get("total_whitened_sq", 0.0) or 0.0)
        review_rows.append(
            {
                "factor_type": row.get("factor_type"),
                "raw_residual_norm": row.get("contribution_norm"),
                "whitened_residual_norm": row.get("contribution_norm"),
                "dimension_normalized_whitened_norm": float(row.get("contribution_norm", 0.0) or 0.0) / max(1.0, (dimension * max(1, count)) ** 0.5),
                "raw_residual_p95": row.get("raw_residual_p95"),
                "whitened_residual_p95": row.get("whitened_residual_p95"),
                "dimension_normalized_whitened_p95": row.get("dimension_normalized_residual_p95"),
                "factor_frequency_count": count,
                "residual_dimension": dimension,
                "total_contribution_proxy_sum_whitened_sq": whitened_sq,
                "contribution_share": whitened_sq / total if total > 0.0 else 0.0,
                "per_dimension_contribution": whitened_sq / max(1, count * dimension),
                "included_in_solver_residual": row.get("included_in_solver_residual"),
                "contribution_status": row.get("contribution_status"),
            }
        )

    by_name = {str(row.get("factor_type")): row for row in review_rows}
    smooth = by_name.get("SmoothnessFactor", {})
    raw = by_name.get("RawDopplerVelocityFactor", {})
    max_norm = max((float(row.get("dimension_normalized_whitened_p95", 0.0) or 0.0) for row in review_rows), default=0.0)
    smooth_share = float(smooth.get("contribution_share", 0.0) or 0.0)
    smooth_norm = float(smooth.get("dimension_normalized_whitened_p95", 0.0) or 0.0)
    if smooth_share >= 0.45 and smooth_norm >= max_norm * 0.95 and smooth_norm > 0.0:
        smooth_classification = "true_residual_dominance"
    elif smooth_share >= 0.45:
        smooth_classification = "count_dominance"
    else:
        smooth_classification = "not_dominant"

    raw_rows = int(raw.get("factor_frequency_count", 0) or 0)
    raw_share = float(raw.get("contribution_share", 0.0) or 0.0)
    if not raw.get("included_in_solver_residual"):
        raw_classification = "activation_missing"
    elif raw_rows > 0 and raw_share < 0.05:
        raw_classification = "weight_too_weak_or_consistent"
    else:
        raw_classification = "active_contribution_visible"

    return {
        "stage": "N8C2_fgo_factor_activation_review",
        "factor_whitening_rows": review_rows,
        "total_contribution_proxy_sum_whitened_sq": total,
        "smoothness_dominance_classification": smooth_classification,
        "raw_doppler_whitening_classification": raw_classification,
        "uses_r_inverse_sqrt_proxy": True,
        "dimension_normalized_review_complete": True,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
