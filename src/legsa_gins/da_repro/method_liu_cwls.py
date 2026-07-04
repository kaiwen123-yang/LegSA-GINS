"""DA03 Liu constrained wrapped least-squares method."""

from __future__ import annotations

from .dd_los_provider import BaselineEpoch
from .method_runner import Go2YawRateEpoch, MethodEstimate, estimate_from_epoch
from .wrapped_ls_solver import wrapped_window_solution


def run(epochs: list[BaselineEpoch], go2_yaw_rates: list[Go2YawRateEpoch] | None = None) -> list[MethodEstimate]:
    estimates: list[MethodEstimate] = []
    yaw = epochs[0].body_yaw_deg if epochs else 0.0
    window: list[BaselineEpoch] = []
    for epoch in epochs:
        if epoch.valid:
            window = (window + [epoch])[-9:]
            weights = [max(row.ratio, 0.5) / max(row.std_e_m + row.std_n_m, 0.05) for row in window]
            yaw = wrapped_window_solution([row.body_yaw_deg for row in window], weights)
            note = "liu_cwls_wrapped_window"
        else:
            note = "liu_cwls_hold_no_valid_dd"
        estimates.append(estimate_from_epoch(epoch, yaw, note))
    return estimates
