"""Combine LSIM and OIM into EKF R scaling.

中文说明：N6A 采用统一观测权重策略，输出 `R_scaled = s * R0`；默认只允许
R inflation，不允许 R shrink，也不做 output-only correction。
"""

from __future__ import annotations

from .lsim_metric import compute_lsim
from .measurement_source_types import ObservationInnovation, SourceAwarePolicyConfig, SourceMetadata, SourceWeightResult
from .oim_metric import compute_oim


def combine_source_weight(
    metadata: SourceMetadata,
    innovation: ObservationInnovation,
    config: SourceAwarePolicyConfig | None = None,
) -> SourceWeightResult:
    cfg = config or SourceAwarePolicyConfig()
    if not cfg.per_source_enabled.get(metadata.source_id, True) or cfg.mode == "off":
        return SourceWeightResult(source_id=metadata.source_id)

    lsim = {"lsim_score": 1.0, "lsim_R_scale": 1.0, "source_blocked": False, "reason_codes": []}
    oim = {
        "innovation_norm": 0.0,
        "normalized_innovation": 0.0,
        "oim_score": 1.0,
        "oim_R_scale": 1.0,
        "reject": False,
        "reason_codes": [],
    }
    if cfg.mode in {"lsim_only", "lsim_oim"} and cfg.per_source_lsim_enabled.get(metadata.source_id, True):
        lsim = compute_lsim(metadata, max_R_scale=cfg.max_R_scale)
    if cfg.mode in {"oim_only", "lsim_oim"} and cfg.per_source_oim_enabled.get(metadata.source_id, True):
        oim = compute_oim(innovation, max_R_scale=cfg.max_R_scale, reject_extreme=cfg.reject_extreme)

    combined = max(float(lsim["lsim_R_scale"]), float(oim["oim_R_scale"]))
    if cfg.no_R_shrink:
        combined = max(1.0, combined)
    combined = min(cfg.max_R_scale, combined)
    reason_codes = tuple(
        reason
        for reason in [*lsim.get("reason_codes", []), *oim.get("reason_codes", [])]
        if reason and reason != "nominal"
    ) or ("nominal",)
    return SourceWeightResult(
        source_id=metadata.source_id,
        lsim_score=float(lsim["lsim_score"]),
        oim_score=float(oim["oim_score"]),
        lsim_R_scale=float(lsim["lsim_R_scale"]),
        oim_R_scale=float(oim["oim_R_scale"]),
        combined_R_scale=combined,
        residual_norm=float(oim["innovation_norm"]),
        normalized_innovation=float(oim["normalized_innovation"]),
        source_blocked=bool(lsim["source_blocked"]),
        reject=bool(lsim["source_blocked"]) or bool(oim["reject"]),
        reason_codes=reason_codes,
    )
