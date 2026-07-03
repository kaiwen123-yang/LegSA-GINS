"""Faithful module reproduction of constrained baseline WLS / GNSS compass."""

from __future__ import annotations

import math

from .method_outputs import EpochOutput
from .provider_factory import ProviderEpoch
from .yaw_frame_contract import baseline_heading_ned_deg, baseline_heading_to_body_yaw_deg, circular_blend_deg


def run_method(epochs: list[ProviderEpoch]) -> list[EpochOutput]:
    if not epochs:
        return []
    valid_lengths = sorted(epoch.baseline_length_m for epoch in epochs if epoch.valid_yaw and epoch.baseline_length_m > 0.05)
    length_prior = valid_lengths[len(valid_lengths) // 2] if valid_lengths else 0.55
    previous_yaw: float | None = None
    outputs: list[EpochOutput] = []
    for epoch in epochs:
        if epoch.valid_yaw:
            scale = length_prior / max(epoch.baseline_length_m, 1e-6)
            constrained_n = epoch.baseline_n_m * scale
            constrained_e = epoch.baseline_e_m * scale
            heading = baseline_heading_ned_deg(constrained_n, constrained_e)
            raw_yaw = baseline_heading_to_body_yaw_deg(heading)
            weight = 1.0 / max(math.radians(epoch.yaw_std_deg) ** 2, 1e-6)
            alpha = min(0.85, max(0.15, weight / (weight + 1.0)))
            yaw = circular_blend_deg(previous_yaw, raw_yaw, alpha)
            previous_yaw = yaw
            update = "constrained_wls_yaw"
            valid = True
        else:
            yaw = previous_yaw
            update = "hold_last_yaw"
            valid = False
        outputs.append(
            EpochOutput(
                time=epoch.time,
                yaw_deg=yaw,
                pos_n_m=None,
                pos_e_m=None,
                pos_u_m=None,
                valid_measurement=valid,
                update_used=update,
            )
        )
    return outputs
