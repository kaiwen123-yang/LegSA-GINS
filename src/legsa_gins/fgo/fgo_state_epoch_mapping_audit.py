"""N8A1 state/epoch mapping audit.

中文说明：本模块明确 state_count 是 epoch 计数还是展开变量计数。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_yaw_convention_audit import as_float, percentile, time_series


STATE_COLUMNS = ["lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]


def audit_state_epoch_mapping(
    *,
    ekf_rows: list[dict[str, Any]],
    fgo_rows: list[dict[str, Any]],
    dataset_report: dict[str, Any] | None = None,
    factor_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    dataset = dataset_report or {}
    factors = factor_rows or []
    epoch_count = len(ekf_rows)
    fgo_epoch_count = len(fgo_rows)
    state_dimension_per_epoch = sum(1 for column in STATE_COLUMNS if any(column in row for row in ekf_rows[:5]))
    state_dimension_per_epoch = state_dimension_per_epoch or len(STATE_COLUMNS)
    expected_variable_count = epoch_count * state_dimension_per_epoch
    reported_state_count = int(dataset.get("state_count", epoch_count) or 0)
    if reported_state_count == epoch_count:
        interpretation = "epoch_count"
    elif reported_state_count == expected_variable_count:
        interpretation = "flattened_variable_count"
    else:
        interpretation = "mismatch"
    times = time_series(ekf_rows)
    dts = [right - left for left, right in zip(times, times[1:])]
    positive_dts = [dt for dt in dts if dt > 0.0]
    median_dt = percentile(positive_dts, 50)
    duplicate_epoch_count = len(times) - len({round(value, 9) for value in times})
    nonmonotonic_count = sum(1 for dt in dts if dt <= 0.0)
    large_gap_count = sum(1 for dt in positive_dts if median_dt > 0.0 and dt > 3.0 * median_dt)
    factor_timestamps = [
        as_float(row.get("time", row.get("timestamp")))
        for row in factors
        if "time" in row or "timestamp" in row
    ]
    factor_time_monotonic = all(right >= left for left, right in zip(factor_timestamps, factor_timestamps[1:]))
    blocker_reasons: list[str] = []
    if epoch_count <= 0:
        blocker_reasons.append("no_ekf_epochs")
    if fgo_epoch_count != epoch_count:
        blocker_reasons.append("fgo_ekf_epoch_count_mismatch")
    if interpretation == "mismatch":
        blocker_reasons.append("reported_state_count_mismatch")
    if nonmonotonic_count:
        blocker_reasons.append("time_nonmonotonic")
    if duplicate_epoch_count:
        blocker_reasons.append("duplicated_epoch_timestamps")
    return {
        "stage": "N8A1_fgo_yaw_delta_policy_review",
        "source_role_alias": "N8A_REPORT_OUTPUT_DIR",
        "state_count_reported": reported_state_count,
        "state_count_interpretation": interpretation,
        "epoch_count": epoch_count,
        "fgo_epoch_count": fgo_epoch_count,
        "state_dimension_per_epoch": state_dimension_per_epoch,
        "variable_count": expected_variable_count,
        "expected_epoch_count": epoch_count,
        "gnss_update_epoch_count_proxy": epoch_count,
        "state_count_equals_epoch_count": reported_state_count == epoch_count,
        "state_count_equals_epoch_count_times_state_dim": reported_state_count == expected_variable_count,
        "missing_epoch_gap_count": large_gap_count,
        "duplicated_epoch_count": duplicate_epoch_count,
        "dt_min": min(positive_dts) if positive_dts else 0.0,
        "dt_p50": median_dt,
        "dt_p95": percentile(positive_dts, 95),
        "dt_max": max(positive_dts) if positive_dts else 0.0,
        "time_monotonic": nonmonotonic_count == 0,
        "nonmonotonic_count": nonmonotonic_count,
        "factor_timestamp_count": len(factor_timestamps),
        "factor_time_monotonic": factor_time_monotonic,
        "blocker_status": "clear" if not blocker_reasons else "state_epoch_mapping_blocker",
        "blocker_reasons": blocker_reasons,
        "epoch_deletion": bool(dataset.get("epoch_deletion", False)),
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "audit_only": True,
        "paper_performance_claim": False,
    }
