"""Classification helpers for BY2 yaw-related degradation types."""

from __future__ import annotations


YAW_DIRECT_TYPES = {f"D{i:02d}" for i in range(30, 39)}
YAW_BASELINE_QUALITY_TYPES = {"D39", "D40", "D41"}
YAW_TIME_TYPES = {"D57"}
YAW_MIXED_TYPES = {"D58", "D59", "D60"}


def yaw_degradation_category(degradation_type_id: str) -> str:
    if degradation_type_id in YAW_DIRECT_TYPES:
        return "direct_yaw_degradation"
    if degradation_type_id in YAW_BASELINE_QUALITY_TYPES:
        return "baseline_quality_or_asymmetry"
    if degradation_type_id in YAW_TIME_TYPES:
        return "timestamp_latency_jitter"
    if degradation_type_id in YAW_MIXED_TYPES:
        return "mixed_or_recovery_yaw_component"
    return "canonical_yaw_preserved"


def requires_yaw_component_validation(degradation_type_id: str) -> bool:
    return yaw_degradation_category(degradation_type_id) != "canonical_yaw_preserved"

