"""Shared N7A Go2 weak-prior types and constants.

中文说明：这些常量只描述 conservative weak prior，不允许把 Go2 position /
velocity / rpy 当作高精度真值。
"""

from __future__ import annotations

import math
from dataclasses import dataclass


GO2_SOURCE_ROLE = "go2_body_state_internal_odometry_and_imu_state"
GO2_ATTITUDE_SOURCE_ID = "go2_attitude_roll_pitch"
DEFAULT_ATTITUDE_STD_DEG = 5.0
DEFAULT_ATTITUDE_STD_RAD = math.radians(DEFAULT_ATTITUDE_STD_DEG)


@dataclass(frozen=True)
class Go2AttitudePriorPolicy:
    """Policy for the only active N7A Go2 prior."""

    std_roll_deg: float = DEFAULT_ATTITUDE_STD_DEG
    std_pitch_deg: float = DEFAULT_ATTITUDE_STD_DEG
    yaw_prior_enabled: bool = False
    position_prior_enabled: bool = False
    velocity_prior_enabled: bool = False
    weak_prior: bool = True
    diagnostic_only: bool = True

    @property
    def std_roll_rad(self) -> float:
        return math.radians(self.std_roll_deg)

    @property
    def std_pitch_rad(self) -> float:
        return math.radians(self.std_pitch_deg)


@dataclass(frozen=True)
class TimeWindow:
    """Closed interval used by N7A time-alignment checks."""

    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def contains(self, value: float) -> bool:
        return self.start <= value <= self.end
