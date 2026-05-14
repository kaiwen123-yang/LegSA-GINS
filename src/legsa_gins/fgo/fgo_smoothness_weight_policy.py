"""N8D smoothness weight policy review.

中文说明：审查 smoothness 是否应拆分/重构，但不把删除 smoothness 当最终捷径。
"""

from __future__ import annotations

from typing import Any


SMOOTHNESS_REVIEW_POLICIES = [
    "weak_yaw_smoothness_from_N8B",
    "split_smoothness_position_velocity_attitude",
    "weaker_yaw_smoothness",
    "process_like_smoothness",
    "no_yaw_smoothness_diagnostic_only",
    "no_smoothness_diagnostic_only",
]


def build_smoothness_weight_policy_report(
    *,
    n8c2_smoothness_report: dict[str, Any],
    variant_report: dict[str, Any],
) -> dict[str, Any]:
    variants = list(variant_report.get("variants", []))
    rows = []
    for summary in variants:
        variant = str(summary.get("variant"))
        if variant not in {"n8b_weak_yaw_default", "balanced_policy_A", "balanced_policy_B", "split_smoothness_best", "no_smoothness_diagnostic", "no_dual_yaw_diagnostic"}:
            continue
        rows.append(
            {
                "variant": variant,
                "smoothness_scale": summary.get("smoothness_scale"),
                "yaw_smoothness_scale": summary.get("yaw_smoothness_scale"),
                "smoothness_share": summary.get("smoothness_contribution_share", 0.0),
                "smoothness_dimension_normalized_whitened_norm": summary.get("smoothness_dimension_normalized_whitened_norm", 0.0),
                "yaw_delta_wrapped_rmse_deg": summary.get("yaw_delta_wrapped_rmse_deg", 0.0),
                "gross_degradation": summary.get("gross_degradation", False),
                "diagnostic_only": summary.get("diagnostic_only", False),
            }
        )
    spike_component = (
        n8c2_smoothness_report.get("component_causing_spikes")
        or n8c2_smoothness_report.get("dominant_component")
        or "yaw_smoothness"
    )
    smoothness_still_dominant = any(float(row.get("smoothness_share", 0.0) or 0.0) >= 0.85 for row in rows)
    return {
        "stage": "N8D_fgo_factor_weight_policy_review",
        "policies_reviewed": SMOOTHNESS_REVIEW_POLICIES,
        "component_rows": rows,
        "n8c2_spike_component": spike_component,
        "yaw_smoothness_still_suspect": "yaw" in str(spike_component).lower(),
        "smoothness_still_dominant": smoothness_still_dominant,
        "position_velocity_smoothness_physically_meaningful": True,
        "recommendations": [
            "keep_weak_yaw_smoothness_for_N8D",
            "split_smoothness_weights",
            "redesign_as_process_kinematic_factor_if_dominance_persists",
            "candidate_N8D2_process_factor_redesign",
        ],
        "no_yaw_no_smoothness_diagnostic_only": True,
        "no_smoothness_final_shortcut": True,
        "trace_weight_tuning": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
        "no_feedback": True,
        "output_substitution": False,
    }
