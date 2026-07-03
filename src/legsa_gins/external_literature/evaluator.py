"""Evaluation for DA2R2 external literature outputs."""

from __future__ import annotations

import math
from statistics import mean

from .method_contracts import MethodContract
from .method_outputs import EpochOutput
from .provider_factory import TraceEpoch, nearest_trace
from .yaw_frame_contract import yaw_residual_deg


def evaluate_outputs(outputs: list[EpochOutput], trace: list[TraceEpoch], method: MethodContract) -> dict[str, object]:
    yaw_errors: list[float] = []
    h_errors: list[float] = []
    u_errors: list[float] = []
    matched = 0
    for item in outputs:
        ref = nearest_trace(trace, item.time)
        if ref is None:
            continue
        matched += 1
        if method.outputs_yaw and item.yaw_deg is not None:
            yaw_errors.append(yaw_residual_deg(item.yaw_deg, ref.yaw_deg))
        if method.outputs_position and item.pos_n_m is not None and item.pos_e_m is not None and item.pos_u_m is not None:
            dn = item.pos_n_m - ref.pos_n_m
            de = item.pos_e_m - ref.pos_e_m
            du = item.pos_u_m - ref.pos_u_m
            h_errors.append(math.hypot(dn, de))
            u_errors.append(du)
    return {
        "epoch_count": len(outputs),
        "matched_reference_count": matched,
        "yaw_rmse_deg": _rmse(yaw_errors),
        "yaw_mae_deg": _mae(yaw_errors),
        "yaw_p95_deg": _p95_abs(yaw_errors),
        "yaw_max_abs_deg": _max_abs(yaw_errors),
        "horizontal_rmse_m": _rmse(h_errors) if method.outputs_position else "not_applicable",
        "up_rmse_m": _rmse(u_errors) if method.outputs_position else "not_applicable",
        "position_metric_applicable": str(method.outputs_position).lower(),
        "yaw_metric_applicable": str(method.outputs_yaw).lower(),
        "wrap_safe": "true",
    }


def _rmse(values: list[float]) -> float | str:
    if not values:
        return "not_available"
    return math.sqrt(mean([value * value for value in values]))


def _mae(values: list[float]) -> float | str:
    if not values:
        return "not_available"
    return mean(abs(value) for value in values)


def _max_abs(values: list[float]) -> float | str:
    if not values:
        return "not_available"
    return max(abs(value) for value in values)


def _p95_abs(values: list[float]) -> float | str:
    if not values:
        return "not_available"
    sorted_abs = sorted(abs(value) for value in values)
    idx = min(len(sorted_abs) - 1, int(math.ceil(0.95 * len(sorted_abs))) - 1)
    return sorted_abs[idx]
