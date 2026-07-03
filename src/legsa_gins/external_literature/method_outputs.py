"""Shared method output records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpochOutput:
    time: float
    yaw_deg: float | None
    pos_n_m: float | None
    pos_e_m: float | None
    pos_u_m: float | None
    valid_measurement: bool
    update_used: str
