"""N6A measurement-source types.

中文说明：source ID 对应 EKF 中真实观测更新路径；N7A 新增 Go2 roll/pitch
弱先验，但仍只做 R inflation，不是输出修正，也不读取评价 trace 或 final_v23 输出。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RECEIVER_POSITION = "receiver_position"
RECEIVER_VELOCITY = "receiver_velocity"
DUAL_ANTENNA_YAW = "dual_antenna_yaw"
RAW_DOPPLER_VELOCITY = "raw_doppler_velocity"
GO2_ATTITUDE_ROLL_PITCH = "go2_attitude_roll_pitch"

OBSERVATION_SOURCE_IDS = [
    RECEIVER_POSITION,
    RECEIVER_VELOCITY,
    DUAL_ANTENNA_YAW,
    RAW_DOPPLER_VELOCITY,
    GO2_ATTITUDE_ROLL_PITCH,
]


@dataclass(frozen=True)
class SourceMetadata:
    source_id: str
    valid: bool = True
    std_n: float | None = None
    std_e: float | None = None
    std_d: float | None = None
    gnss_status: str | None = None
    pvt_valid: bool | None = None
    yaw_std: float | None = None
    yaw_residual_mode: str | None = None
    rel_valid: bool | None = None
    ant_valid: bool | None = None
    ant_state: str | None = None
    baseline_length_m: float | None = None
    rel_acc_m: float | None = None
    sat_count: int | None = None
    provider_status: str | None = None
    residual_norm: float | None = None
    time_diff: float | None = None
    quality_flag: str | None = None
    covariance_available: bool | None = True
    spike_candidate: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObservationInnovation:
    source_id: str
    residual: tuple[float, ...] = ()
    r_trace: float = 1.0
    hph_trace: float = 0.0


@dataclass(frozen=True)
class SourceWeightResult:
    source_id: str
    lsim_score: float = 1.0
    oim_score: float = 1.0
    lsim_R_scale: float = 1.0
    oim_R_scale: float = 1.0
    combined_R_scale: float = 1.0
    residual_norm: float = 0.0
    normalized_innovation: float = 0.0
    source_blocked: bool = False
    reject: bool = False
    reason_codes: tuple[str, ...] = ("nominal",)


@dataclass(frozen=True)
class SourceAwarePolicyConfig:
    mode: str = "lsim_oim"
    max_R_scale: float = 25.0
    no_R_shrink: bool = True
    reject_extreme: bool = False
    per_source_enabled: dict[str, bool] = field(
        default_factory=lambda: {source_id: True for source_id in OBSERVATION_SOURCE_IDS}
    )
    per_source_lsim_enabled: dict[str, bool] = field(
        default_factory=lambda: {source_id: True for source_id in OBSERVATION_SOURCE_IDS}
    )
    per_source_oim_enabled: dict[str, bool] = field(
        default_factory=lambda: {source_id: True for source_id in OBSERVATION_SOURCE_IDS}
    )


def std_values(metadata: SourceMetadata) -> tuple[float, float, float]:
    """Return finite source standard deviations with a conservative floor."""

    values = []
    for value in (metadata.std_n, metadata.std_e, metadata.std_d):
        if isinstance(value, (int, float)) and value > 0:
            values.append(float(value))
        else:
            values.append(1.0)
    return tuple(values)  # type: ignore[return-value]
