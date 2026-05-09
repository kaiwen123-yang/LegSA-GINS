"""Gap screen for N4H4R3 source-backed port clean replay.

中文说明：失败时只分类，不调参、不删 epoch、不做 output-only correction。
"""

from __future__ import annotations

from typing import Any


def _metric(summary: dict[str, Any], key: str) -> float | None:
    value = summary.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def make_port_gap_screen(
    summary: dict[str, Any],
    manifest: dict[str, Any] | None = None,
    input_status: dict[str, Any] | None = None,
    run_status: str = "completed",
) -> dict[str, Any]:
    manifest = manifest or {}
    input_status = input_status or {}
    blocking: list[str] = []
    categories: list[str] = []

    if input_status.get("clean_input_missing"):
        categories.append("input_config")
        blocking.append("clean_input_missing")
    if run_status != "completed":
        categories.append("runtime_loop")
        blocking.append(f"port_core_run_{run_status}")
    if summary.get("count", 0) == 0:
        categories.append("output_evaluation")
        blocking.append("no_aligned_eval_rows")

    propagation = int(manifest.get("propagation_count", 0) or 0)
    measurement = int(manifest.get("measurement_update_count", 0) or 0)
    position = int(manifest.get("position_update_count", 0) or 0)
    velocity = int(manifest.get("velocity_update_count", 0) or 0)
    yaw = int(manifest.get("yaw_update_count", 0) or 0)
    yaw_reject = int(manifest.get("yaw_REJECT", 0) or 0)
    if propagation == 0:
        categories.append("runtime_loop")
        blocking.append("propagation_count_zero")
    if measurement == 0:
        categories.append("runtime_loop")
        blocking.append("measurement_update_count_zero")
    expected_gnss = int(input_status.get("clean_gnss_row_count", 0) or 0)
    if expected_gnss and measurement and measurement < max(1, int(0.8 * expected_gnss)):
        categories.append("runtime_loop")
        blocking.append("gnss_rows_skipped_unexpectedly")
    if position == 0:
        categories.append("runtime_loop")
        blocking.append("position_update_count_zero")
    if velocity == 0:
        categories.append("runtime_loop")
        blocking.append("velocity_update_count_zero")
    if yaw == 0:
        categories.append("runtime_loop")
        blocking.append("yaw_update_count_zero")
    yaw_reject_ratio = yaw_reject / yaw if yaw else None
    if yaw_reject_ratio is not None and yaw_reject_ratio > 0.5:
        categories.append("runtime_loop")
        blocking.append("yaw_reject_ratio_too_high")

    if (_metric(summary, "horizontal_rmse_m") or 0.0) > 10.0:
        categories.append("filter")
        blocking.append("position_divergence_gt_10m")
    elif (_metric(summary, "horizontal_rmse_m") or 0.0) > 2.0:
        categories.append("filter")
        blocking.append("horizontal_gate_failed")
    if (_metric(summary, "up_rmse_m") or 0.0) > 10.0:
        categories.append("filter")
        blocking.append("vertical_divergence_gt_10m")
    elif (_metric(summary, "up_rmse_m") or 0.0) > 3.0:
        categories.append("filter")
        blocking.append("up_gate_failed")
    if (_metric(summary, "yaw_rmse_deg") or 0.0) > 10.0:
        categories.append("filter")
        blocking.append("yaw_divergence_gt_10deg")
    elif (_metric(summary, "yaw_rmse_deg") or 0.0) > 2.0:
        categories.append("filter")
        blocking.append("yaw_gate_failed")
    if max(_metric(summary, "roll_rmse_deg") or 0.0, _metric(summary, "pitch_rmse_deg") or 0.0) > 10.0:
        categories.append("filter")
        blocking.append("roll_pitch_divergence_gt_10deg")
    elif max(_metric(summary, "roll_rmse_deg") or 0.0, _metric(summary, "pitch_rmse_deg") or 0.0) > 1.6:
        categories.append("filter")
        blocking.append("roll_pitch_relaxed_gate_failed")

    categories = sorted(set(categories))
    if "input_config" in categories:
        recommendation = "N4H4R3_config_input_fix"
    elif "runtime_loop" in categories and (
        "measurement_update_count_zero" in blocking
        or "position_update_count_zero" in blocking
        or "gnss_rows_skipped_unexpectedly" in blocking
    ):
        recommendation = "N4H4R3_update_count_fix"
    elif "output_evaluation" in categories:
        recommendation = "N4H4R3_writer_evaluator_fix"
    elif "filter" in categories:
        recommendation = "N4H4R3_filter_math_gap_fix"
    else:
        recommendation = "N4H4E_visual_validation_if_passed"

    return {
        "phase": "N4H4R3",
        "gap_categories": categories,
        "blocking_issues": blocking,
        "recommended_next_stage": recommendation,
        "update_counts": {
            "clean_gnss_row_count": expected_gnss,
            "propagation_count": propagation,
            "measurement_update_count": measurement,
            "position_update_count": position,
            "velocity_update_count": velocity,
            "yaw_update_count": yaw,
            "yaw_NORMAL": int(manifest.get("yaw_NORMAL", 0) or 0),
            "yaw_DOWNWEIGHT": int(manifest.get("yaw_DOWNWEIGHT", 0) or 0),
            "yaw_REJECT": yaw_reject,
            "yaw_reject_ratio": yaw_reject_ratio,
        },
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
    }
