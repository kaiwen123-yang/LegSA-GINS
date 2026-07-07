"""DA01 full-backend classic-case policies and summaries."""

from __future__ import annotations

import bisect
import math
from copy import deepcopy
from typing import Any

import numpy as np

from .common import percentile, rmse, wrap180, wrap360
from .evaluator import load_epoch_output, load_trace_yaw
from .method_teunissen_clambda import CLASSIC_CASES, METHOD_ID
from .yaw_frame_contract import body_yaw_from_lateral_baseline


FULL_BACKEND_REPRODUCTION_LEVEL = "FAITHFUL_NON_OFFICIAL_ALGORITHM"
FULL_BACKEND_PROVIDER_LAYER = "raw_carrier_dd_los"


def classic_case_manifest_rows() -> list[dict[str, Any]]:
    return [
        {
            "case_id": case.case_id,
            "case_family": case.case_family,
            "policy": case.policy,
            "seed": "" if case.seed is None else case.seed,
            "method_id": METHOD_ID,
            "method_mode": "full_backend",
            "provider_layer_used": FULL_BACKEND_PROVIDER_LAYER,
        }
        for case in CLASSIC_CASES
    ]


def _rng(seed: int | None) -> np.random.Generator:
    return np.random.default_rng(0 if seed is None else int(seed))


def _refresh_geometry(row: dict[str, Any], *, yaw_offset_deg: float, nominal_length_m: float | None = None) -> None:
    east = float(row["baseline_east_m"])
    north = float(row["baseline_north_m"])
    up = float(row.get("baseline_up_m", 0.0))
    length = math.sqrt(east * east + north * north + up * up)
    if nominal_length_m is not None and length > 1.0e-12:
        scale = nominal_length_m / length
        east *= scale
        north *= scale
        up *= scale
        row["baseline_east_m"] = east
        row["baseline_north_m"] = north
        row["baseline_up_m"] = up
        length = nominal_length_m
    heading = wrap360(math.degrees(math.atan2(east, north)))
    row["baseline_length_m"] = length
    row["baseline_heading_deg"] = heading
    row["body_yaw_deg"] = body_yaw_from_lateral_baseline(heading, offset_deg=yaw_offset_deg)


def _apply_vector_noise(rows: list[dict[str, Any]], *, seed: int | None, sigma_m: float, nominal_length_m: float, yaw_offset_deg: float) -> None:
    rng = _rng(seed)
    for row in rows:
        row["baseline_east_m"] = float(row["baseline_east_m"]) + float(rng.normal(0.0, sigma_m))
        row["baseline_north_m"] = float(row["baseline_north_m"]) + float(rng.normal(0.0, sigma_m))
        row["baseline_up_m"] = float(row.get("baseline_up_m", 0.0)) + float(rng.normal(0.0, sigma_m * 0.5))
        _refresh_geometry(row, yaw_offset_deg=yaw_offset_deg, nominal_length_m=nominal_length_m)


def _apply_position_spikes(
    rows: list[dict[str, Any]],
    *,
    seed: int | None,
    magnitude_m: float,
    fraction: float,
    nominal_length_m: float,
    yaw_offset_deg: float,
) -> int:
    if not rows:
        return 0
    rng = _rng(seed)
    count = max(1, int(len(rows) * fraction))
    for index in rng.choice(len(rows), size=count, replace=False):
        row = rows[int(index)]
        angle = float(rng.uniform(0.0, 2.0 * math.pi))
        row["baseline_east_m"] = float(row["baseline_east_m"]) + magnitude_m * math.cos(angle)
        row["baseline_north_m"] = float(row["baseline_north_m"]) + magnitude_m * math.sin(angle)
        _refresh_geometry(row, yaw_offset_deg=yaw_offset_deg, nominal_length_m=nominal_length_m)
    return count


def _rotate_horizontal(row: dict[str, Any], delta_deg: float, *, yaw_offset_deg: float, nominal_length_m: float) -> None:
    east = float(row["baseline_east_m"])
    north = float(row["baseline_north_m"])
    up = float(row.get("baseline_up_m", 0.0))
    angle = math.radians(delta_deg)
    row["baseline_east_m"] = east * math.cos(angle) + north * math.sin(angle)
    row["baseline_north_m"] = -east * math.sin(angle) + north * math.cos(angle)
    row["baseline_up_m"] = up
    _refresh_geometry(row, yaw_offset_deg=yaw_offset_deg, nominal_length_m=nominal_length_m)


def _apply_yaw_spikes(
    rows: list[dict[str, Any]],
    *,
    seed: int | None,
    magnitude_deg: float,
    fraction: float,
    nominal_length_m: float,
    yaw_offset_deg: float,
) -> int:
    if not rows:
        return 0
    rng = _rng(seed)
    count = max(1, int(len(rows) * fraction))
    for index in rng.choice(len(rows), size=count, replace=False):
        sign = -1.0 if rng.random() < 0.5 else 1.0
        _rotate_horizontal(rows[int(index)], sign * magnitude_deg, yaw_offset_deg=yaw_offset_deg, nominal_length_m=nominal_length_m)
    return count


def _downsample(rows: list[dict[str, Any]], min_dt_sec: float) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    last_time: float | None = None
    for row in rows:
        t = float(row["timestamp"])
        if last_time is None or t - last_time >= min_dt_sec:
            kept.append(row)
            last_time = t
    return kept


def apply_full_backend_case_policy(
    base_rows: list[dict[str, Any]],
    case_id: str,
    *,
    nominal_length_m: float,
    yaw_offset_deg: float = 90.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case = next(case for case in CLASSIC_CASES if case.case_id == case_id)
    rows = [deepcopy(row) for row in base_rows]
    rows.sort(key=lambda row: float(row["timestamp"]))
    policy_report: dict[str, Any] = {
        "case_id": case.case_id,
        "case_family": case.case_family,
        "policy": case.policy,
        "seed": case.seed,
        "input_rows": len(rows),
        "trace_modified": False,
        "trace_used_online": False,
        "provider_input_modified": case.policy != "none",
        "epoch_deleted_for_metric": False,
    }
    if case.policy == "outage_10s" and rows:
        midpoint = float(rows[len(rows) // 2]["timestamp"])
        rows = [row for row in rows if not (midpoint <= float(row["timestamp"]) < midpoint + 10.0)]
        policy_report["source_measurement_withheld_rows"] = policy_report["input_rows"] - len(rows)
    elif case.policy == "downsample_2hz":
        rows = _downsample(rows, 0.50)
        policy_report["source_measurement_withheld_rows"] = policy_report["input_rows"] - len(rows)
    elif case.policy == "downsample_1hz":
        rows = _downsample(rows, 0.95)
        policy_report["source_measurement_withheld_rows"] = policy_report["input_rows"] - len(rows)
    elif case.policy == "position_noise_medium":
        _apply_vector_noise(rows, seed=case.seed, sigma_m=0.05, nominal_length_m=nominal_length_m, yaw_offset_deg=yaw_offset_deg)
    elif case.policy == "position_spike_medium":
        policy_report["spike_rows"] = _apply_position_spikes(
            rows,
            seed=case.seed,
            magnitude_m=0.25,
            fraction=0.05,
            nominal_length_m=nominal_length_m,
            yaw_offset_deg=yaw_offset_deg,
        )
    elif case.policy == "std_inflation_strong":
        for row in rows:
            row["provider_std_scale"] = 4.0
        policy_report["provider_std_scale"] = 4.0
    elif case.policy == "yaw_spike_10_deg":
        policy_report["yaw_spike_rows"] = _apply_yaw_spikes(
            rows,
            seed=case.seed,
            magnitude_deg=10.0,
            fraction=0.05,
            nominal_length_m=nominal_length_m,
            yaw_offset_deg=yaw_offset_deg,
        )
    elif case.policy == "yawstd_inflation_2x":
        for row in rows:
            row["provider_yaw_std_scale"] = 2.0
        policy_report["provider_yaw_std_scale"] = 2.0
    elif case.policy == "mixed_medium":
        _apply_vector_noise(rows, seed=case.seed, sigma_m=0.03, nominal_length_m=nominal_length_m, yaw_offset_deg=yaw_offset_deg)
        policy_report["spike_rows"] = _apply_position_spikes(
            rows,
            seed=case.seed,
            magnitude_m=0.15,
            fraction=0.03,
            nominal_length_m=nominal_length_m,
            yaw_offset_deg=yaw_offset_deg,
        )
        policy_report["yaw_spike_rows"] = _apply_yaw_spikes(
            rows,
            seed=case.seed,
            magnitude_deg=6.0,
            fraction=0.03,
            nominal_length_m=nominal_length_m,
            yaw_offset_deg=yaw_offset_deg,
        )
    for row in rows:
        row["case_id"] = case.case_id
        row["method_mode"] = "full_backend"
        row["provider_layer_used"] = FULL_BACKEND_PROVIDER_LAYER
        row["trace_used_online"] = False
        row["status_diagnostic_used_as_full_backend"] = False
        row["full_backend_claim"] = True
    policy_report["output_rows"] = len(rows)
    return rows, policy_report


def dd_provider_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    num_dd = [float(row["num_dd"]) for row in rows if row.get("num_dd") not in (None, "")]
    ranks = [int(row["design_rank"]) for row in rows if row.get("design_rank") not in (None, "")]
    conditions = [
        float(row["design_condition_number"])
        for row in rows
        if row.get("design_condition_number") not in (None, "") and math.isfinite(float(row["design_condition_number"]))
    ]
    return {
        "usable_dd_epochs": len(rows),
        "median_num_dd": percentile(num_dd, 0.50),
        "rank3_epoch_count": sum(1 for rank in ranks if rank >= 3),
        "median_condition_number": percentile(conditions, 0.50),
        "max_condition_number": max(conditions) if conditions else None,
    }


def baseline_physical_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [float(row["baseline_length_m"]) for row in rows if row.get("baseline_length_m") not in (None, "")]
    median = percentile(lengths, 0.50)
    physical_pass = median is not None and 0.20 <= median <= 0.60
    four_meter = any(3.5 <= value <= 4.5 for value in lengths)
    return {
        "median_baseline_length_m": median,
        "p05_baseline_length_m": percentile(lengths, 0.05),
        "p95_baseline_length_m": percentile(lengths, 0.95),
        "baseline_physical_gate_pass": physical_pass,
        "four_meter_baseline_reappeared": four_meter,
        "physical_gate_min_m": 0.20,
        "physical_gate_max_m": 0.60,
    }


def _nearest_trace(trace_rows: list[dict[str, float]], t: float) -> tuple[dict[str, float], float] | None:
    if not trace_rows:
        return None
    times = [row["time"] for row in trace_rows]
    index = bisect.bisect_left(times, t)
    candidates = []
    if index < len(trace_rows):
        candidates.append(trace_rows[index])
    if index > 0:
        candidates.append(trace_rows[index - 1])
    if not candidates:
        return None
    best = min(candidates, key=lambda row: abs(row["time"] - t))
    return best, t - best["time"]


def evaluate_yaw_with_max(epoch_output: str, trace_reference: str, *, max_dt: float = 0.10) -> dict[str, Any]:
    est_rows = load_epoch_output(epoch_output)
    trace_rows = load_trace_yaw(trace_reference)
    errors: list[float] = []
    dt_values: list[float] = []
    for est in est_rows:
        match = _nearest_trace(trace_rows, est["time"])
        if match is None:
            continue
        ref, dt = match
        if abs(dt) > max_dt:
            continue
        errors.append(wrap180(est["yaw_deg"] - ref["yaw_deg"]))
        dt_values.append(dt)
    abs_errors = [abs(value) for value in errors]
    return {
        "evaluation_mode": "yaw_only_position_not_applicable",
        "estimate_row_count": len(est_rows),
        "trace_row_count": len(trace_rows),
        "aligned_count": len(errors),
        "max_alignment_dt_sec": max((abs(value) for value in dt_values), default=None),
        "yaw_rmse_deg": rmse(errors),
        "yaw_mae_deg": sum(abs_errors) / len(abs_errors) if abs_errors else None,
        "yaw_p95_abs_deg": percentile(abs_errors, 0.95),
        "yaw_max_abs_deg": max(abs_errors) if abs_errors else None,
        "position_metrics": "not_applicable",
        "trace_used_online": False,
        "trace_evaluation_only": True,
        "trace_used_for_sign_or_offset": False,
        "receiver_imu_data_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
    }
