"""DA05 affine MILS single-baseline method."""

from __future__ import annotations

from .baseline_constraint import median_length, project_horizontal_to_length
from .dd_los_provider import BaselineEpoch
from .method_runner import Go2YawRateEpoch, MethodEstimate, estimate_from_epoch, yaw_update
from .yaw_frame_contract import GNSS2_TO_GNSS1_RIGHT_CONTRACT


def run(epochs: list[BaselineEpoch], go2_yaw_rates: list[Go2YawRateEpoch] | None = None) -> list[MethodEstimate]:
    nominal = median_length([row.baseline_length_m for row in epochs if row.valid])
    yaw = epochs[0].body_yaw_deg if epochs else 0.0
    estimates: list[MethodEstimate] = []
    for epoch in epochs:
        if epoch.valid:
            e, n = project_horizontal_to_length(epoch.baseline_e_m, epoch.baseline_n_m, nominal)
            measurement = GNSS2_TO_GNSS1_RIGHT_CONTRACT.body_yaw_deg(e, n)
            gain = 0.75 if epoch.q == 1 else 0.45
            yaw = yaw_update(yaw, measurement, gain)
            note = "affine_mils_single_baseline_projection"
        else:
            note = "affine_mils_hold_no_valid_dd"
        estimates.append(estimate_from_epoch(epoch, yaw, note))
    return estimates
