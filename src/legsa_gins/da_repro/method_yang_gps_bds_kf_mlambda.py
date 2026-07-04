"""DA02 Yang GPS/BDS baseline-length KF/MLAMBDA-style method."""

from __future__ import annotations

from .baseline_constraint import median_length
from .dd_los_provider import BaselineEpoch
from .method_runner import Go2YawRateEpoch, MethodEstimate, estimate_from_epoch, yaw_update


def run(epochs: list[BaselineEpoch], go2_yaw_rates: list[Go2YawRateEpoch] | None = None) -> list[MethodEstimate]:
    nominal_length = median_length([row.baseline_length_m for row in epochs if row.valid])
    yaw = epochs[0].body_yaw_deg if epochs else 0.0
    variance = 25.0
    last_time = epochs[0].time if epochs else 0.0
    estimates: list[MethodEstimate] = []
    for epoch in epochs:
        dt = max(epoch.time - last_time, 0.0)
        variance += max(dt, 0.2) * 0.25
        if epoch.valid:
            length_penalty = abs(epoch.baseline_length_m - nominal_length) * 12.0 if nominal_length else 1.0
            ambiguity_bonus = 0.35 if epoch.q == 1 else 1.0
            ratio_bonus = 1.0 / max(epoch.ratio, 0.5)
            meas_var = max(0.4, 1.5 + length_penalty + ratio_bonus) * ambiguity_bonus
            gain = variance / (variance + meas_var)
            yaw = yaw_update(yaw, epoch.body_yaw_deg, min(max(gain, 0.05), 0.95))
            variance = (1.0 - gain) * variance
            note = "yang_kf_mlambda_update"
        else:
            note = "yang_kf_predict_no_valid_dd"
        estimates.append(estimate_from_epoch(epoch, yaw, note))
        last_time = epoch.time
    return estimates
