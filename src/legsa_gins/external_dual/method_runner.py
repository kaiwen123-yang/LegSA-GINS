"""Method dispatch for A1 yaw-only external dual-antenna matrix rows."""

from __future__ import annotations

import hashlib
import math
from bisect import bisect_left
from dataclasses import dataclass

from .go2_body_provider import Go2BodyEpoch
from .method_contracts import MethodContract
from .status_dual_yaw_provider import DualYawEpoch
from .trace_reference_adapter import TraceYawEpoch, nearest_trace_yaw
from .yaw_frame_adapter import circular_mean_deg, wrap360_deg, yaw_error_deg


@dataclass(frozen=True)
class EpochEstimate:
    time: float
    method_yaw_deg: float | None
    measurement_yaw_deg: float | None
    reference_yaw_deg: float | None
    yaw_error_deg: float | None
    valid_measurement: bool
    notes: str


@dataclass(frozen=True)
class _Estimate:
    time: float
    method_yaw_deg: float
    notes: str


def run_method_case(method: MethodContract, case: dict[str, str], status_epochs: list[DualYawEpoch], trace_epochs: list[TraceYawEpoch], go2_epochs: list[Go2BodyEpoch]) -> list[EpochEstimate]:
    degraded = [_degrade_epoch(epoch, case) for epoch in status_epochs]
    if method.method_id == "DA02_LIU_CONSTRAINED_WRAPPED_WLS":
        estimates = _run_wrapped_wls(degraded)
    elif method.method_id == "DA03_YANG_BASELINE_KF_STATUS":
        estimates = _run_baseline_kf(degraded)
    elif method.method_id == "DA04_WU_ROBUST_EQKF_GO2":
        estimates = _run_robust_eqkf(degraded, go2_epochs)
    else:
        raise ValueError(f"unsupported method: {method.method_id}")
    out: list[EpochEstimate] = []
    for estimate, measurement in estimates:
        reference = nearest_trace_yaw(trace_epochs, estimate.time)
        reference_yaw = reference.yaw_deg if reference else None
        error = yaw_error_deg(estimate.method_yaw_deg, reference_yaw) if reference_yaw is not None else None
        out.append(EpochEstimate(estimate.time, estimate.method_yaw_deg, measurement.body_yaw_deg if measurement.valid else None, reference_yaw, error, measurement.valid, estimate.notes))
    return out


def _run_wrapped_wls(epochs: list[DualYawEpoch]) -> list[tuple[_Estimate, DualYawEpoch]]:
    out: list[tuple[_Estimate, DualYawEpoch]] = []
    window: list[DualYawEpoch] = []
    last_yaw = epochs[0].body_yaw_deg if epochs else 0.0
    for epoch in epochs:
        if epoch.valid:
            window = (window + [epoch])[-7:]
            yaw = circular_mean_deg([item.body_yaw_deg for item in window], [1.0 / max(item.rel_acc_m, 0.02) for item in window])
            last_yaw = yaw
            notes = "wrapped_wls_update"
        else:
            yaw = last_yaw
            notes = "hold_last_no_valid_measurement"
        out.append((_Estimate(epoch.time, yaw, notes), epoch))
    return out


def _run_baseline_kf(epochs: list[DualYawEpoch]) -> list[tuple[_Estimate, DualYawEpoch]]:
    out: list[tuple[_Estimate, DualYawEpoch]] = []
    yaw = epochs[0].body_yaw_deg if epochs else 0.0
    variance = 25.0
    nominal_length = _median([epoch.baseline_length_m for epoch in epochs if epoch.valid]) or 0.35
    last_time = epochs[0].time if epochs else 0.0
    for epoch in epochs:
        variance += max(epoch.time - last_time, 0.1) * 0.35
        if epoch.valid:
            meas_var = max(0.5, 1.5 + abs(epoch.baseline_length_m - nominal_length) * 20.0 + epoch.rel_acc_m * 30.0)
            gain = variance / (variance + meas_var)
            yaw = wrap360_deg(yaw + gain * yaw_error_deg(epoch.body_yaw_deg, yaw))
            variance = (1.0 - gain) * variance
            notes = "baseline_length_kf_update"
        else:
            notes = "kf_predict_no_valid_measurement"
        last_time = epoch.time
        out.append((_Estimate(epoch.time, yaw, notes), epoch))
    return out


def _run_robust_eqkf(epochs: list[DualYawEpoch], go2_epochs: list[Go2BodyEpoch]) -> list[tuple[_Estimate, DualYawEpoch]]:
    out: list[tuple[_Estimate, DualYawEpoch]] = []
    yaw = epochs[0].body_yaw_deg if epochs else 0.0
    variance = 16.0
    last_time = epochs[0].time if epochs else 0.0
    go2_times = [epoch.time for epoch in go2_epochs]
    for epoch in epochs:
        dt = max(epoch.time - last_time, 0.0)
        yaw = wrap360_deg(yaw + math.degrees(_nearest_yaw_rate(go2_epochs, go2_times, epoch.time) * dt))
        variance += max(dt, 0.1) * 0.8
        if epoch.valid:
            innovation = yaw_error_deg(epoch.body_yaw_deg, yaw)
            huber = min(1.0, 8.0 / max(abs(innovation), 1e-6))
            meas_var = max(0.75, 2.0 + epoch.rel_acc_m * 25.0) / max(huber, 0.1)
            gain = variance / (variance + meas_var)
            yaw = wrap360_deg(yaw + gain * innovation)
            variance = (1.0 - gain) * variance
            notes = "robust_eqkf_yaw_rate_predict_dual_yaw_update"
        else:
            notes = "robust_eqkf_predict_no_valid_measurement"
        last_time = epoch.time
        out.append((_Estimate(epoch.time, yaw, notes), epoch))
    return out


def _degrade_epoch(epoch: DualYawEpoch, case: dict[str, str]) -> DualYawEpoch:
    dtype = case.get("degradation_type_id", "")
    case_id = case.get("case_id", "")
    seed = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:8], 16)
    idx = int(round(epoch.time * 10.0))
    valid = epoch.valid
    yaw = epoch.body_yaw_deg
    rel_acc = epoch.rel_acc_m
    if dtype in {"D01", "D02", "D03", "D04", "D05", "D06"} and (idx + seed) % (23 + seed % 11) < 3 + int(dtype[-1]):
        valid = False
    elif dtype in {"D07", "D08", "D09", "D10", "D11", "D12"}:
        keep_mod = {"D07": 2, "D08": 3, "D09": 5, "D10": 10, "D11": 4, "D12": 6}[dtype]
        valid = valid and (idx + seed) % keep_mod == 0
    elif dtype in {"D13", "D14"}:
        scale = 0.8 if dtype == "D13" else 1.8
        raw = int(hashlib.sha256(f"{case_id}:{epoch.time:.3f}".encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        yaw = wrap360_deg(yaw + (raw * 2.0 - 1.0) * scale)
        rel_acc += 0.03 if dtype == "D13" else 0.08
    return DualYawEpoch(epoch.time, epoch.gnss2_time, epoch.dt_s, epoch.baseline_n_m, epoch.baseline_e_m, epoch.baseline_d_m, epoch.baseline_length_m, rel_acc, epoch.baseline_heading_deg, yaw, valid)


def _nearest_yaw_rate(go2_epochs: list[Go2BodyEpoch], go2_times: list[float], time_s: float) -> float:
    if not go2_epochs:
        return 0.0
    pos = bisect_left(go2_times, time_s)
    candidates = []
    if pos < len(go2_epochs):
        candidates.append(go2_epochs[pos])
    if pos:
        candidates.append(go2_epochs[pos - 1])
    if not candidates:
        return 0.0
    best = min(candidates, key=lambda epoch: abs(epoch.time - time_s))
    return best.yaw_speed_rad_s if abs(best.time - time_s) <= 1.5 else 0.0


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else 0.5 * (values[mid - 1] + values[mid])
