"""Faithful non-official two-receiver IEKF-style simplified EKF."""

from __future__ import annotations

import math

import numpy as np

from .method_outputs import EpochOutput
from .provider_factory import ProviderEpoch
from .yaw_frame_contract import wrap180_deg, wrap360_deg


def run_method(epochs: list[ProviderEpoch]) -> list[EpochOutput]:
    if not epochs:
        return []
    first = epochs[0]
    x = np.array([first.pos_n_m, first.pos_e_m, first.pos_u_m, first.vel_n_mps, first.vel_e_mps, first.vel_u_mps, math.radians(first.body_yaw_meas_deg)], dtype=float)
    p = np.diag([4.0, 4.0, 2.0, 1.0, 1.0, 0.5, math.radians(30.0) ** 2])
    q = np.diag([0.04, 0.04, 0.02, 0.15, 0.15, 0.05, math.radians(2.0) ** 2])
    outputs: list[EpochOutput] = []
    prev_time = first.time
    for epoch in epochs:
        dt = max(0.0, min(epoch.time - prev_time, 2.0))
        prev_time = epoch.time
        f = np.eye(7)
        f[0, 3] = dt
        f[1, 4] = dt
        f[2, 5] = dt
        x = f @ x
        x[6] = math.radians(wrap360_deg(math.degrees(x[6]) + math.degrees(epoch.yaw_rate_rad_s * dt)))
        p = f @ p @ f.T + q
        updates: list[str] = []
        if epoch.valid_position:
            z = np.array([epoch.pos_n_m, epoch.pos_e_m, epoch.pos_u_m])
            h = np.zeros((3, 7))
            h[0, 0] = h[1, 1] = h[2, 2] = 1.0
            r = np.diag([epoch.pos_std_m**2, epoch.pos_std_m**2, max(0.4, epoch.pos_std_m) ** 2])
            x, p = _linear_update(x, p, h, z, r)
            updates.append("position")
        if epoch.valid_yaw:
            h = np.zeros((1, 7))
            h[0, 6] = 1.0
            innovation = math.radians(wrap180_deg(epoch.body_yaw_meas_deg - math.degrees(x[6])))
            z = np.array([x[6] + innovation])
            r = np.array([[math.radians(max(epoch.yaw_std_deg, 0.5)) ** 2]])
            x, p = _linear_update(x, p, h, z, r)
            x[6] = math.radians(wrap360_deg(math.degrees(x[6])))
            updates.append("dual_yaw")
        outputs.append(
            EpochOutput(
                time=epoch.time,
                yaw_deg=wrap360_deg(math.degrees(x[6])),
                pos_n_m=float(x[0]),
                pos_e_m=float(x[1]),
                pos_u_m=float(x[2]),
                valid_measurement=bool(updates),
                update_used="+".join(updates) if updates else "prediction_only",
            )
        )
    return outputs


def _linear_update(x: np.ndarray, p: np.ndarray, h: np.ndarray, z: np.ndarray, r: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    innovation = z - h @ x
    s = h @ p @ h.T + r
    k = p @ h.T @ np.linalg.inv(s)
    x = x + k @ innovation
    p = (np.eye(p.shape[0]) - k @ h) @ p
    return x, p
