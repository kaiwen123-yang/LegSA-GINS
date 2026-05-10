"""Local/Source-Level Integrity Metric for N6A.

中文说明：LSIM 是来源级质量度量，只使用观测源自身 metadata；不使用 trace、
final_v23 output 或评价误差。默认策略只放大 R，不缩小 baseline R。
"""

from __future__ import annotations

import math

from .measurement_source_types import (
    DUAL_ANTENNA_YAW,
    RAW_DOPPLER_VELOCITY,
    RECEIVER_POSITION,
    RECEIVER_VELOCITY,
    SourceMetadata,
    std_values,
)


def _cap(scale: float, max_scale: float) -> float:
    return max(1.0, min(float(max_scale), float(scale) if math.isfinite(scale) else float(max_scale)))


def compute_lsim(metadata: SourceMetadata, *, max_R_scale: float = 25.0) -> dict[str, object]:
    """Compute LSIM score and conservative R scale.

    中文说明：invalid source 可 block；suspicious source 仅保守降权，N6A 不允许 R shrink。
    """

    reasons: list[str] = []
    scale = 1.0
    source_blocked = False
    if not metadata.valid:
        source_blocked = True
        scale = max_R_scale
        reasons.append("lsim_invalid_source")
    if metadata.covariance_available is False:
        scale = max(scale, 4.0)
        reasons.append("lsim_covariance_missing")
    if metadata.time_diff is not None and abs(metadata.time_diff) > 0.08:
        scale = max(scale, 3.0)
        reasons.append("lsim_time_alignment_suspicious")
    if metadata.quality_flag and metadata.quality_flag not in {"nominal", "available"}:
        scale = max(scale, 2.0)
        reasons.append("lsim_quality_flag_suspicious")

    std_max = max(std_values(metadata))
    if metadata.source_id == RECEIVER_POSITION:
        if metadata.gnss_status and metadata.gnss_status.lower() in {"invalid", "none", "bad"}:
            source_blocked = True
            scale = max_R_scale
            reasons.append("lsim_receiver_position_status_invalid")
        if std_max > 5.0:
            scale = max(scale, min(10.0, std_max / 0.5))
            reasons.append("lsim_receiver_position_std_high")
    elif metadata.source_id == RECEIVER_VELOCITY:
        if metadata.pvt_valid is False:
            source_blocked = True
            scale = max_R_scale
            reasons.append("lsim_receiver_velocity_pvt_invalid")
        if std_max > 0.6:
            scale = max(scale, min(10.0, std_max / 0.1))
            reasons.append("lsim_receiver_velocity_std_high")
    elif metadata.source_id == DUAL_ANTENNA_YAW:
        yaw_std = abs(float(metadata.yaw_std or std_max))
        if metadata.rel_valid is False or metadata.ant_valid is False or metadata.ant_state in {"invalid", "bad"}:
            scale = max(scale, 6.0)
            reasons.append("lsim_dual_yaw_antenna_state_suspicious")
        if yaw_std > math.radians(3.0):
            scale = max(scale, min(10.0, yaw_std / math.radians(0.5)))
            reasons.append("lsim_dual_yaw_std_high")
    elif metadata.source_id == RAW_DOPPLER_VELOCITY:
        if metadata.provider_status not in {None, "available"}:
            source_blocked = True
            scale = max_R_scale
            reasons.append("lsim_raw_doppler_provider_unavailable")
        if metadata.sat_count is not None and metadata.sat_count < 8:
            scale = max(scale, 4.0)
            reasons.append("lsim_raw_doppler_sat_count_low")
        if std_max > 0.5:
            scale = max(scale, min(10.0, std_max / 0.05))
            reasons.append("lsim_raw_doppler_std_high")
        if metadata.spike_candidate:
            scale = max(scale, 2.0)
            reasons.append("lsim_solver_visible_spike_candidate")

    scale = _cap(scale, max_R_scale)
    return {
        "lsim_score": max(0.0, min(1.0, 1.0 / scale)),
        "lsim_R_scale": scale,
        "source_blocked": source_blocked,
        "reason_codes": reasons or ["nominal"],
    }
