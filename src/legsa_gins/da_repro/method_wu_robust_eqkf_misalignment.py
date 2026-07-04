"""DA04 Wu robust EQKF with simplified misalignment compensation."""

from __future__ import annotations

import math

from .dd_los_provider import BaselineEpoch
from .method_runner import Go2YawRateEpoch, MethodEstimate, estimate_from_epoch, nearest_yaw_rate, yaw_update


def run(epochs: list[BaselineEpoch], go2_yaw_rates: list[Go2YawRateEpoch] | None = None) -> list[MethodEstimate]:
    go2_yaw_rates = go2_yaw_rates or []
    go2_times = [row.time for row in go2_yaw_rates]
    yaw = epochs[0].body_yaw_deg if epochs else 0.0
    misalignment = 0.0
    variance = 36.0
    last_time = epochs[0].time if epochs else 0.0
    estimates: list[MethodEstimate] = []
    for epoch in epochs:
        dt = max(epoch.time - last_time, 0.0)
        yaw = (yaw + math.degrees(nearest_yaw_rate(go2_yaw_rates, go2_times, epoch.time) * dt) + misalignment * dt) % 360.0
        variance += max(dt, 0.2) * 0.8
        if epoch.valid:
            innovation = ((epoch.body_yaw_deg - yaw + 180.0) % 360.0) - 180.0
            huber = min(1.0, 8.0 / max(abs(innovation), 1e-6))
            meas_var = max(0.8, 3.0 / max(huber, 0.1) + 1.0 / max(epoch.ratio, 0.5))
            gain = variance / (variance + meas_var)
            yaw = yaw_update(yaw, epoch.body_yaw_deg, min(max(gain, 0.03), 0.85))
            misalignment = 0.995 * misalignment + 0.005 * innovation / max(dt, 0.2)
            variance = (1.0 - gain) * variance
            note = "wu_robust_eqkf_dual_yaw_update"
        else:
            note = "wu_robust_eqkf_predict_no_valid_dd"
        estimates.append(estimate_from_epoch(epoch, yaw, note))
        last_time = epoch.time
    return estimates
