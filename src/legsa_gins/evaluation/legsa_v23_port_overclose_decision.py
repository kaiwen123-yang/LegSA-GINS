"""Decision logic for N4H4R3B over-close audit.

中文说明：决策优先排除 measurement-copy、reference leak 和 covariance/config
问题；只有这些证据通过后，metric gate pass 才能进入带 caveat 的视觉验证。
"""

from __future__ import annotations

from typing import Any


def make_overclose_decision(
    overclose_report: dict[str, Any],
    measurement_copy_report: dict[str, Any],
    reference_independence_report: dict[str, Any],
    covariance_config_report: dict[str, Any],
    residual_gain_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    residual_gain_report = residual_gain_report or {}
    blocking: list[str] = []
    if measurement_copy_report.get("measurement_copy_suspect") or measurement_copy_report.get("output_substitution_suspect"):
        recommended = "N4H4R3C_writer_measurement_copy_fix"
        parity_status = "blocked_by_measurement_copy_suspect"
        blocking.append("measurement_copy_or_output_substitution_suspect")
    elif not reference_independence_report.get("reference_independence_ok", False):
        recommended = "N4H4R3C_reference_evaluator_fix"
        parity_status = "blocked_by_reference_independence"
        blocking.append("reference_independence_failed")
    elif covariance_config_report.get("covariance_config_mismatch", False):
        recommended = "N4H4R3C_covariance_config_parity_fix"
        parity_status = "blocked_by_covariance_config_mismatch"
        blocking.append("covariance_config_mismatch")
    elif residual_gain_report.get("over_tight_measurement_update_suspect", False):
        recommended = "N4H4R3C_residual_gain_parity_fix"
        parity_status = "blocked_by_over_tight_measurement_update"
        blocking.append("over_tight_measurement_update_suspect")
    elif overclose_report.get("metric_gate_passed", False):
        recommended = "N4H4E_visual_validation_with_external_closeness_caveat"
        parity_status = "metric_pass_external_closeness_failed"
        if overclose_report.get("external_closeness_failed", False):
            blocking.append("external_clean_closeness_failed")
    else:
        recommended = "N4H4R3B_extend_overclose_audit"
        parity_status = "evidence_insufficient_or_metric_gate_failed"
        blocking.append("evidence_insufficient")

    return {
        "phase": "N4H4R3B",
        "recommended_next_stage": recommended,
        "parity_status": parity_status,
        "engineering_backbone_candidate": bool(
            overclose_report.get("metric_gate_passed", False)
            and not measurement_copy_report.get("measurement_copy_suspect", False)
            and not measurement_copy_report.get("output_substitution_suspect", False)
            and reference_independence_report.get("reference_independence_ok", False)
            and not covariance_config_report.get("covariance_config_mismatch", False)
            and not residual_gain_report.get("over_tight_measurement_update_suspect", False)
        ),
        "blocking_issues": blocking,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
