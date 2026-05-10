"""Observation Innovation Metric for N6A.

中文说明：OIM 基于 residual 与 R/HPH 的一致性，不能用 trace、final_v23
输出或 N5D1 spike 时间调参；spike 时间只允许在事后 audit 中查响应。
"""

from __future__ import annotations

import math

from .measurement_source_types import ObservationInnovation


def innovation_norm(residual: tuple[float, ...] | list[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in residual))


def compute_oim(
    innovation: ObservationInnovation,
    *,
    max_R_scale: float = 25.0,
    reject_extreme: bool = False,
) -> dict[str, object]:
    """Compute innovation consistency and conservative R scale."""

    residual_norm = innovation_norm(innovation.residual)
    denom = math.sqrt(max(1.0e-12, float(innovation.r_trace) + float(innovation.hph_trace)))
    normalized = residual_norm / denom
    reasons: list[str] = []
    scale = 1.0
    reject = False
    if normalized > 1.5:
        scale = 1.0 + (normalized - 1.5) ** 2
    if normalized > 3.0:
        scale = max(scale, normalized * normalized / 3.0)
        reasons.append("oim_high_normalized_innovation")
    if innovation.source_id == "raw_doppler_velocity" and normalized > 2.0:
        reasons.append("oim_raw_doppler_innovation_suspicious")
    if reject_extreme and normalized > 8.0:
        reject = True
        reasons.append("oim_extreme_reject")
    scale = max(1.0, min(max_R_scale, scale))
    return {
        "innovation_norm": residual_norm,
        "normalized_innovation": normalized,
        "oim_score": max(0.0, min(1.0, 1.0 / scale)),
        "oim_R_scale": scale,
        "reject": reject,
        "reason_codes": reasons or ["nominal"],
    }
