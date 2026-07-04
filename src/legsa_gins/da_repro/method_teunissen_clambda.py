"""DA01 C-LAMBDA-style constrained integer baseline method."""

from __future__ import annotations

from .baseline_constraint import median_length, project_horizontal_to_length
from .dd_los_provider import BaselineEpoch
from .method_runner import Go2YawRateEpoch, MethodEstimate, estimate_from_epoch, yaw_update
from .yaw_frame_contract import GNSS2_TO_GNSS1_RIGHT_CONTRACT


def run(epochs: list[BaselineEpoch], go2_yaw_rates: list[Go2YawRateEpoch] | None = None) -> list[MethodEstimate]:
    target_length = median_length([row.baseline_length_m for row in epochs if row.valid and row.q in {1, 2}])
    estimates: list[MethodEstimate] = []
    yaw = epochs[0].body_yaw_deg if epochs else 0.0
    for epoch in epochs:
        if epoch.valid:
            e, n = project_horizontal_to_length(epoch.baseline_e_m, epoch.baseline_n_m, target_length)
            constrained_yaw = GNSS2_TO_GNSS1_RIGHT_CONTRACT.body_yaw_deg(e, n)
            gain = 1.0 if epoch.q == 1 and epoch.ratio >= 3.0 else 0.55 if epoch.q == 2 else 0.30
            yaw = yaw_update(yaw, constrained_yaw, gain)
            note = "clambda_fixed_ratio" if epoch.q == 1 else "clambda_float_constrained"
        else:
            note = "clambda_hold_no_valid_dd"
        estimates.append(estimate_from_epoch(epoch, yaw, note))
    return estimates
