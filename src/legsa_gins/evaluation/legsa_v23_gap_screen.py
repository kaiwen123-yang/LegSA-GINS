"""N4H4D gap screen for LegSA-v23 clean replay.

中文说明：gap screen 只分类失败原因和推荐下一阶段，不调参、不删 epoch、
不做 output-only correction。
"""

from __future__ import annotations

from typing import Any


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _count(manifest: dict[str, Any], key: str) -> int:
    value = manifest.get(key)
    return int(value) if isinstance(value, (int, float)) else 0


def screen_gap(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    runner_report: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """中文说明：根据输入、运行、输出和误差规模分类 N4H4D 差距。"""

    runner = runner_report or {}
    blockers: list[str] = []
    categories: list[str] = []
    recommendations: list[str] = []

    if runner.get("clean_input_status") == "clean_input_missing":
        blockers.append("clean_input_missing")
        categories.append("input_config")
        recommendations.append("N4H4D_input_config_fix")
    if runner.get("dual_reference_status") == "reference_missing":
        blockers.append("reference_reconstruction_failure")
        categories.append("output_evaluation")
        recommendations.append("N4H4D_output_evaluator_fix")

    if _count(manifest, "measurement_update_count") == 0:
        blockers.append("measurement_update_count_zero")
        categories.append("runtime")
        recommendations.append("N4H4D_update_trigger_fix")
    if _count(manifest, "yaw_update_count") == 0:
        blockers.append("yaw_update_count_zero")
        categories.append("runtime")
        recommendations.append("N4H4D_yaw_update_convention_fix")
    if _count(manifest, "velocity_update_count") == 0:
        blockers.append("velocity_update_count_zero")
        categories.append("runtime")
        recommendations.append("N4H4D_update_trigger_fix")
    if _count(manifest, "state_feedback_implemented") == 0 and manifest.get("state_feedback_implemented") is not True:
        blockers.append("state_feedback_not_applied")
        categories.append("runtime")
        recommendations.append("N4H4D_state_feedback_sign_fix")

    yaw_reject = _count(manifest, "yaw_reject_count")
    yaw_total = max(1, _count(manifest, "yaw_update_count"))
    if yaw_reject / yaw_total > 0.5:
        blockers.append("yaw_scheme_rejects_too_many_updates")
        categories.append("runtime")
        recommendations.append("N4H4D_yaw_update_convention_fix")

    count = _count(summary, "count")
    if count == 0:
        blockers.append("aligned_count_zero")
        categories.append("output_evaluation")
        recommendations.append("N4H4D_output_evaluator_fix")

    horizontal = _num(summary.get("horizontal_rmse_m"))
    up = _num(summary.get("up_rmse_m"))
    yaw = _num(summary.get("yaw_rmse_deg"))
    roll = _num(summary.get("roll_rmse_deg"))
    pitch = _num(summary.get("pitch_rmse_deg"))
    if horizontal is not None and horizontal > 10.0:
        blockers.append("position_diverges_gt_10m")
        categories.append("mechanization_update")
        recommendations.append("N4H4D_mechanization_debug")
    if up is not None and abs(up) > 10.0:
        blockers.append("vertical_drifts_gt_10m")
        categories.append("mechanization_update")
        recommendations.append("N4H4D_mechanization_debug")
    if yaw is not None and yaw > 10.0:
        blockers.append("yaw_diverges_gt_10deg")
        categories.append("mechanization_update")
        recommendations.append("N4H4D_yaw_update_convention_fix")
    if (roll is not None and roll > 10.0) or (pitch is not None and pitch > 10.0):
        blockers.append("roll_pitch_explode")
        categories.append("mechanization_update")
        recommendations.append("N4H4D_mechanization_debug")

    classification = (decision or {}).get("parity_classification", "parity_failed")
    if classification == "parity_passed" and not blockers:
        recommendations.append("N4H4E_visual_validation_if_parity_passed")
    elif not recommendations:
        recommendations.append("N4H4D_time_alignment_fix")
        blockers.append("parity_gap_unclassified")
        categories.append("runtime")

    unique_categories = sorted(set(categories)) or ["none"]
    unique_recommendations = list(dict.fromkeys(recommendations))
    return {
        "phase": "N4H4D",
        "gap_screen_status": "no_blocking_gap" if classification == "parity_passed" and not blockers else "gap_detected",
        "gap_classification": unique_categories,
        "blocking_issues": list(dict.fromkeys(blockers)),
        "recommended_next_stage": unique_recommendations[0],
        "recommended_next_stages": unique_recommendations,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
