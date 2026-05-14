"""N8C2 Go2ProprioceptiveJointFactor activation review.

中文说明：Go2 joint 因子只做激活和贡献诊断，不声明 Go2 为真值。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_factor_activation_audit import write_json_report


def _row(report: dict[str, Any], factor: str) -> dict[str, Any]:
    return next((row for row in report.get("factor_activation_rows", []) if row.get("factor_type") == factor), {})


def build_go2_joint_factor_activation_review(*, activation_report: dict[str, Any]) -> dict[str, Any]:
    row = _row(activation_report, "Go2ProprioceptiveJointFactor")
    delta = float(row.get("on_off_delta_combined_abs", 0.0) or 0.0)
    if not row.get("included_in_solver_residual"):
        classification = "activation_missing"
    elif delta <= 0.05 and float(row.get("whitened_residual_p95", 0.0) or 0.0) > 0.0:
        classification = "consistent_no_large_delta"
    elif float(row.get("contribution_share", 0.0) or 0.0) < 0.10:
        classification = "weak_but_active"
    else:
        classification = "active_but_dominated"
    return {
        "stage": "N8C2_fgo_factor_activation_review",
        "factor_type": "Go2ProprioceptiveJointFactor",
        "residual_rows": row.get("residual_row_count", 0),
        "attitude_residual_p95": row.get("raw_residual_p95", 0.0),
        "horizontal_velocity_residual_p95": row.get("raw_residual_p95", 0.0),
        "h_blocks": row.get("touched_state_blocks", []),
        "r_stats": row.get("r_covariance_stats", {}),
        "whitened_residual_stats": row.get("whitened_residual_stats", {}),
        "on_off_variant_true_toggle": bool(row.get("on_off_variant_exists")),
        "source_aware_scale": "none_in_n8c2_no_feedback_smoother",
        "contribution_status": row.get("contribution_status"),
        "classification": classification,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
