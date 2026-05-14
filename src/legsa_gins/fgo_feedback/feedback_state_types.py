"""Shared N8G feedback state types.

中文说明：这些类型只描述 solver 可见的 EKF/FGO feedback 状态，不包含 trace
或 final_v23 输出，也不承载论文性能结论。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


FEEDBACK_OBSERVATION_COLUMNS = [
    "time",
    "pN",
    "pE",
    "pD",
    "vN",
    "vE",
    "vD",
    "roll",
    "pitch",
    "yaw",
    "std_pN",
    "std_pE",
    "std_pD",
    "std_vN",
    "std_vE",
    "std_vD",
    "std_roll",
    "std_pitch",
    "std_yaw",
    "source_window_start",
    "source_window_end",
    "feedback_valid",
    "window_epoch_count",
    "feedback_mode",
]


@dataclass(frozen=True)
class NavStateSample:
    time: float
    lat_deg: float
    lon_deg: float
    height_m: float
    vn_mps: float
    ve_mps: float
    vd_mps: float
    roll_deg: float
    pitch_deg: float
    yaw_deg: float


@dataclass(frozen=True)
class SlidingWindow:
    feedback_time: float
    window_start: float
    window_end: float
    sample_indices: tuple[int, ...]
    no_future_data_verified: bool

    @property
    def window_epoch_count(self) -> int:
        return len(self.sample_indices)


@dataclass(frozen=True)
class FeedbackObservation:
    time: float
    pN: float
    pE: float
    pD: float
    vN: float
    vE: float
    vD: float
    roll: float
    pitch: float
    yaw: float
    std_pN: float
    std_pE: float
    std_pD: float
    std_vN: float
    std_vE: float
    std_vD: float
    std_roll: float
    std_pitch: float
    std_yaw: float
    source_window_start: float
    source_window_end: float
    feedback_valid: bool
    window_epoch_count: int
    feedback_mode: str

    def to_csv_row(self) -> dict[str, Any]:
        row = {name: getattr(self, name) for name in FEEDBACK_OBSERVATION_COLUMNS if name != "feedback_valid"}
        row["feedback_valid"] = "1" if self.feedback_valid else "0"
        return row

    def with_validity(self, valid: bool) -> "FeedbackObservation":
        return FeedbackObservation(
            time=self.time,
            pN=self.pN,
            pE=self.pE,
            pD=self.pD,
            vN=self.vN,
            vE=self.vE,
            vD=self.vD,
            roll=self.roll,
            pitch=self.pitch,
            yaw=self.yaw,
            std_pN=self.std_pN,
            std_pE=self.std_pE,
            std_pD=self.std_pD,
            std_vN=self.std_vN,
            std_vE=self.std_vE,
            std_vD=self.std_vD,
            std_roll=self.std_roll,
            std_pitch=self.std_pitch,
            std_yaw=self.std_yaw,
            source_window_start=self.source_window_start,
            source_window_end=self.source_window_end,
            feedback_valid=valid,
            window_epoch_count=self.window_epoch_count,
            feedback_mode=self.feedback_mode,
        )


@dataclass(frozen=True)
class FeedbackGateThresholds:
    max_position_correction_m: float = 6.0
    max_velocity_correction_mps: float = 1.5
    max_attitude_correction_deg: float = 8.0
    max_yaw_correction_deg: float = 8.0
    min_window_epoch_count: int = 3
    min_interval_s: float = 0.5


@dataclass(frozen=True)
class FeedbackVariantSpec:
    variant_id: str
    feedback_mode: str
    position_enabled: bool = False
    velocity_enabled: bool = False
    attitude_enabled: bool = False
    reject_all: bool = False
    diagnostic_only: bool = False


def finite_float(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def wrap_degrees(value: float) -> float:
    wrapped = float(value)
    while wrapped > 180.0:
        wrapped -= 360.0
    while wrapped <= -180.0:
        wrapped += 360.0
    return wrapped


def angle_delta_deg(lhs: float, rhs: float) -> float:
    return wrap_degrees(float(lhs) - float(rhs))


def norm(values: tuple[float, ...] | list[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in values))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = int(round((len(ordered) - 1) * max(0.0, min(1.0, q))))
    return ordered[index]


def stats(values: list[float]) -> dict[str, float]:
    return {
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "max": max(values) if values else 0.0,
    }


def mode_state_blocks(mode: str) -> dict[str, bool]:
    normalized = mode.lower()
    return {
        "position": "position" in normalized,
        "velocity": "velocity" in normalized,
        "attitude": "attitude" in normalized,
    }


def manifest_false_flags(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("fgo_feedback_output_substitution") is False
        and payload.get("fgo_feedback_direct_nav_override") is False
        and payload.get("trace_solver_input") is False
        and payload.get("final_v23_output_solver_input") is False
        and payload.get("paper_performance_claim") is False
    )
