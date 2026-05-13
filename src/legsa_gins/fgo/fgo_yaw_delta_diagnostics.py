"""N8A1 yaw-delta diagnostic summaries.

中文说明：本模块定位 FGO 与 EKF yaw delta 的时间段和候选原因。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_yaw_convention_audit import (
    as_float,
    percentile,
    rmse,
    time_series,
    unwrap_degrees,
    wrap_delta_deg,
    yaw_delta_deg,
    yaw_series,
)


def _segment_indices(count: int, segments: int = 8) -> list[tuple[int, int]]:
    if count <= 0:
        return []
    segment_count = max(1, min(segments, count))
    bounds: list[tuple[int, int]] = []
    for segment in range(segment_count):
        start = int(round(segment * count / segment_count))
        end = int(round((segment + 1) * count / segment_count))
        if end > start:
            bounds.append((start, end))
    return bounds


def diagnose_yaw_delta(
    *,
    ekf_rows: list[dict[str, Any]],
    fgo_rows: list[dict[str, Any]],
    yaw_convention_report: dict[str, Any] | None = None,
    factor_policy_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    convention = yaw_convention_report or {}
    factor_policy = factor_policy_report or {}
    ekf_yaw = yaw_series(ekf_rows)
    fgo_yaw = yaw_series(fgo_rows)
    times = time_series(ekf_rows)
    count = min(len(ekf_yaw), len(fgo_yaw), len(times))
    ekf_yaw = ekf_yaw[:count]
    fgo_yaw = fgo_yaw[:count]
    times = times[:count]
    raw_delta = [fgo - ekf for ekf, fgo in zip(ekf_yaw, fgo_yaw)]
    wrapped_delta = [yaw_delta_deg(fgo, ekf) for ekf, fgo in zip(ekf_yaw, fgo_yaw)]
    ekf_unwrapped = unwrap_degrees(ekf_yaw)
    fgo_unwrapped = unwrap_degrees(fgo_yaw)
    unwrapped_delta = [fgo - ekf for ekf, fgo in zip(ekf_unwrapped, fgo_unwrapped)]
    abs_wrapped = [abs(value) for value in wrapped_delta]
    segment_rows: list[dict[str, Any]] = []
    for start, end in _segment_indices(count):
        values = wrapped_delta[start:end]
        abs_values = [abs(value) for value in values]
        segment_rows.append(
            {
                "segment_index": len(segment_rows),
                "start_index": start,
                "end_index": end - 1,
                "start_time": times[start] if times else None,
                "end_time": times[end - 1] if times else None,
                "yaw_delta_rmse_deg": rmse(values),
                "yaw_delta_abs_p95_deg": percentile(abs_values, 95),
                "sample_count": len(values),
            }
        )
    worst_segment = max(segment_rows, key=lambda row: as_float(row.get("yaw_delta_rmse_deg")), default={})
    mean_delta = sum(wrapped_delta) / len(wrapped_delta) if wrapped_delta else 0.0
    wrapped_rmse = rmse(wrapped_delta)
    constant_bias_suspect = bool(wrapped_rmse > 5.0 and abs(mean_delta) > 0.75 * wrapped_rmse)
    fgo_step = [abs(wrap_delta_deg(right - left)) for left, right in zip(fgo_yaw, fgo_yaw[1:])]
    ekf_step = [abs(wrap_delta_deg(right - left)) for left, right in zip(ekf_yaw, ekf_yaw[1:])]
    smoothness_drift_suspect = bool(percentile(fgo_step, 95) > max(30.0, 3.0 * percentile(ekf_step, 95)))
    wrap_jump_suspect = convention.get("blocker_status") in {"yaw_wrap_residual_blocker", "yaw_unit_blocker"} or convention.get("yaw_jump_count", 0) > 0
    candidate_stack_suspect = bool(factor_policy.get("candidate_factor_leak_suspect", False))
    dual_yaw_factor_policy_suspect = bool(percentile(abs_wrapped, 95) > 15.0 and not candidate_stack_suspect)
    if wrap_jump_suspect:
        primary_hypothesis = "yaw_wrap_or_residual_convention"
    elif candidate_stack_suspect:
        primary_hypothesis = "diagnostic_candidate_factor_leak"
    elif smoothness_drift_suspect:
        primary_hypothesis = "smoothness_yaw_policy"
    elif dual_yaw_factor_policy_suspect:
        primary_hypothesis = "dual_yaw_factor_weight_policy"
    elif constant_bias_suspect:
        primary_hypothesis = "constant_yaw_bias"
    else:
        primary_hypothesis = "no_single_dominant_source"
    return {
        "stage": "N8A1_fgo_yaw_delta_policy_review",
        "source_role_alias": "N8A_REPORT_OUTPUT_DIR",
        "aligned_state_count": count,
        "yaw_delta_rmse_raw_deg": rmse(raw_delta),
        "yaw_delta_rmse_wrapped_deg": wrapped_rmse,
        "yaw_delta_rmse_unwrapped_deg": rmse(unwrapped_delta),
        "yaw_delta_abs_p50_deg": percentile(abs_wrapped, 50),
        "yaw_delta_abs_p95_deg": percentile(abs_wrapped, 95),
        "yaw_delta_abs_max_deg": max(abs_wrapped) if abs_wrapped else 0.0,
        "yaw_delta_mean_wrapped_deg": mean_delta,
        "constant_bias_suspect": constant_bias_suspect,
        "wrap_jump_suspect": wrap_jump_suspect,
        "smoothness_drift_suspect": smoothness_drift_suspect,
        "candidate_stack_suspect": candidate_stack_suspect,
        "dual_yaw_factor_policy_suspect": dual_yaw_factor_policy_suspect,
        "primary_hypothesis": primary_hypothesis,
        "segment_count": len(segment_rows),
        "segments": segment_rows,
        "worst_segment": worst_segment,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "audit_only": True,
        "paper_performance_claim": False,
    }
