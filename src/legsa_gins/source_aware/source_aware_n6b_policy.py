"""N6B conservative source-aware LSIM/OIM policy.

中文说明：N6B OIM 使用创新协方差 ``S = HPH^T + R`` 计算 NIS；
LSIM 只使用 metadata，不使用 residual、trace、final_v23 output 或评价误差。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from statistics import median
from typing import Any, Sequence

from .measurement_source_types import (
    DUAL_ANTENNA_YAW,
    OBSERVATION_SOURCE_IDS,
    RAW_DOPPLER_VELOCITY,
    RECEIVER_POSITION,
    RECEIVER_VELOCITY,
    SourceMetadata,
    std_values,
)


POLICY_VERSION = "n6b_conservative_innovation_covariance"


@dataclass(frozen=True)
class N6BPolicyConfig:
    policy_version: str = POLICY_VERSION
    mode: str = "lsim_oim"
    use_innovation_covariance: bool = True
    deadband_normalized: float = 1.5
    moderate_normalized: float = 2.5
    strong_normalized: float = 4.0
    receiver_position_cap: float = 5.0
    receiver_velocity_cap: float = 8.0
    dual_yaw_cap: float = 10.0
    raw_doppler_cap: float = 15.0
    global_cap: float = 25.0
    no_R_shrink: bool = True
    reject_extreme: bool = False
    enable_rolling_innovation_baseline: bool = True
    rolling_window_size: int = 31
    rolling_mad_floor: float = 0.5
    per_source_enabled: dict[str, bool] = field(
        default_factory=lambda: {source_id: True for source_id in OBSERVATION_SOURCE_IDS}
    )
    per_source_lsim_enabled: dict[str, bool] = field(
        default_factory=lambda: {source_id: True for source_id in OBSERVATION_SOURCE_IDS}
    )
    per_source_oim_enabled: dict[str, bool] = field(
        default_factory=lambda: {source_id: True for source_id in OBSERVATION_SOURCE_IDS}
    )


@dataclass(frozen=True)
class InnovationCovarianceInput:
    source_id: str
    residual: tuple[float, ...]
    hph: tuple[tuple[float, ...], ...]
    r: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class N6BPolicyResult:
    source_id: str
    policy_version: str = POLICY_VERSION
    lsim_R_scale: float = 1.0
    oim_R_scale: float = 1.0
    combined_R_scale: float = 1.0
    normalized_innovation: float = 0.0
    nis: float = 0.0
    dof: int = 0
    innovation_cov_trace: float = 0.0
    used_innovation_covariance: bool = True
    source_cap: float = 1.0
    rolling_normalized_median: float = 0.0
    rolling_normalized_mad: float = 0.0
    relative_anomaly_score: float = 0.0
    reject: bool = False
    reason_codes: tuple[str, ...] = ("nominal",)
    paper_performance_claim: bool = False


def source_cap(source_id: str, config: N6BPolicyConfig | None = None) -> float:
    cfg = config or N6BPolicyConfig()
    caps = {
        RECEIVER_POSITION: cfg.receiver_position_cap,
        RECEIVER_VELOCITY: cfg.receiver_velocity_cap,
        DUAL_ANTENNA_YAW: cfg.dual_yaw_cap,
        RAW_DOPPLER_VELOCITY: cfg.raw_doppler_cap,
    }
    return max(1.0, min(float(cfg.global_cap), float(caps.get(source_id, cfg.global_cap))))


def _cap(scale: float, source_id: str, config: N6BPolicyConfig) -> float:
    value = float(scale) if math.isfinite(float(scale)) else source_cap(source_id, config)
    if config.no_R_shrink:
        value = max(1.0, value)
    return min(source_cap(source_id, config), max(1.0, value))


def _inverse(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(matrix)
    work = [[0.0 for _ in range(2 * n)] for _ in range(n)]
    for r, row in enumerate(matrix):
        if len(row) != n:
            raise ValueError("innovation covariance must be square")
        for c, value in enumerate(row):
            work[r][c] = float(value)
        work[r][n + r] = 1.0
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(work[r][col]))
        if abs(work[pivot][col]) < 1.0e-15:
            raise ValueError("singular innovation covariance")
        if pivot != col:
            work[col], work[pivot] = work[pivot], work[col]
        diag = work[col][col]
        for c in range(2 * n):
            work[col][c] /= diag
        for r in range(n):
            if r == col:
                continue
            factor = work[r][col]
            for c in range(2 * n):
                work[r][c] -= factor * work[col][c]
    return [row[n:] for row in work]


def _mat_vec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    return [sum(float(a) * float(b) for a, b in zip(row, vector)) for row in matrix]


def _trace(matrix: Sequence[Sequence[float]]) -> float:
    return sum(float(matrix[i][i]) for i in range(min(len(matrix), len(matrix[0]) if matrix else 0)))


def _add_matrix(lhs: Sequence[Sequence[float]], rhs: Sequence[Sequence[float]]) -> list[list[float]]:
    if len(lhs) != len(rhs):
        raise ValueError("matrix row mismatch")
    out: list[list[float]] = []
    for lrow, rrow in zip(lhs, rhs):
        if len(lrow) != len(rrow):
            raise ValueError("matrix column mismatch")
        out.append([float(a) + float(b) for a, b in zip(lrow, rrow)])
    return out


def compute_innovation_covariance_metrics(evidence: InnovationCovarianceInput) -> dict[str, Any]:
    """Return NIS and normalized innovation from S=HPH^T+R."""

    residual = tuple(float(value) for value in evidence.residual)
    s_matrix = _add_matrix(evidence.hph, evidence.r)
    weighted = _mat_vec(_inverse(s_matrix), residual)
    nis = max(0.0, sum(a * b for a, b in zip(residual, weighted)))
    dof = max(1, len(residual))
    return {
        "nis": nis,
        "dof": dof,
        "normalized_innovation": math.sqrt(max(0.0, nis / dof)),
        "innovation_cov_trace": _trace(s_matrix),
        "used_innovation_covariance": True,
    }


def compute_lsim_n6b(metadata: SourceMetadata, config: N6BPolicyConfig | None = None) -> dict[str, Any]:
    """Compute metadata-only LSIM scale for N6B."""

    cfg = config or N6BPolicyConfig()
    reasons: list[str] = []
    scale = 1.0
    reject = False
    stds = std_values(metadata)
    finite_std = all(math.isfinite(value) and value > 0.0 for value in stds)
    std_max = max(abs(value) for value in stds)
    if not metadata.valid:
        reject = True
        scale = source_cap(metadata.source_id, cfg)
        reasons.append("lsim_invalid_source")
    if metadata.covariance_available is False:
        scale = max(scale, 1.5)
        reasons.append("lsim_covariance_missing")
    if not finite_std:
        scale = max(scale, 1.5)
        reasons.append("lsim_std_nonfinite_or_missing")
    if metadata.time_diff is not None and abs(float(metadata.time_diff)) > 0.08:
        scale = max(scale, 2.5 if abs(float(metadata.time_diff)) > 0.25 else 1.5)
        reasons.append("lsim_time_alignment_suspicious")
    if metadata.quality_flag and metadata.quality_flag not in {"nominal", "available"}:
        scale = max(scale, 1.5)
        reasons.append("lsim_quality_flag_suspicious")

    if metadata.source_id == RECEIVER_POSITION:
        if std_max > 50.0:
            scale = max(scale, 5.0)
            reasons.append("lsim_receiver_position_std_extreme")
        elif std_max > 25.0:
            scale = max(scale, 2.0)
            reasons.append("lsim_receiver_position_std_high")
    elif metadata.source_id == RECEIVER_VELOCITY:
        if std_max > 6.0:
            scale = max(scale, 4.0)
            reasons.append("lsim_receiver_velocity_std_extreme")
        elif std_max > 3.0:
            scale = max(scale, 2.0)
            reasons.append("lsim_receiver_velocity_std_high")
    elif metadata.source_id == DUAL_ANTENNA_YAW:
        yaw_std = abs(float(metadata.yaw_std or std_max))
        if metadata.rel_valid is False or metadata.ant_valid is False or metadata.ant_state in {"invalid", "bad"}:
            scale = max(scale, 2.0)
            reasons.append("lsim_dual_yaw_antenna_state_suspicious")
        if yaw_std > math.radians(30.0):
            scale = max(scale, 6.0)
            reasons.append("lsim_dual_yaw_std_extreme")
        elif yaw_std > math.radians(15.0):
            scale = max(scale, 2.0)
            reasons.append("lsim_dual_yaw_std_high")
    elif metadata.source_id == RAW_DOPPLER_VELOCITY:
        if metadata.provider_status not in {None, "available"}:
            reject = True
            scale = source_cap(metadata.source_id, cfg)
            reasons.append("lsim_raw_doppler_provider_unavailable")
        if metadata.sat_count is not None and metadata.sat_count < 5:
            scale = max(scale, 3.0)
            reasons.append("lsim_raw_doppler_sat_count_very_low")
        elif metadata.sat_count is not None and metadata.sat_count < 8:
            scale = max(scale, 1.5)
            reasons.append("lsim_raw_doppler_sat_count_low")
        if std_max > 2.0:
            scale = max(scale, 4.0)
            reasons.append("lsim_raw_doppler_std_extreme")
        elif std_max > 1.0:
            scale = max(scale, 2.0)
            reasons.append("lsim_raw_doppler_std_high")
        if metadata.spike_candidate:
            scale = max(scale, 1.25)
            reasons.append("lsim_solver_visible_spike_candidate")
    scale = _cap(scale, metadata.source_id, cfg)
    return {"lsim_R_scale": scale, "reject": reject, "reason_codes": reasons or ["nominal"]}


def compute_oim_n6b(
    evidence: InnovationCovarianceInput,
    config: N6BPolicyConfig | None = None,
    *,
    rolling_history: Sequence[float] = (),
) -> dict[str, Any]:
    cfg = config or N6BPolicyConfig()
    metrics = compute_innovation_covariance_metrics(evidence)
    normalized = float(metrics["normalized_innovation"])
    reasons: list[str] = []
    scale = 1.0
    if normalized > cfg.deadband_normalized:
        delta = normalized - cfg.deadband_normalized
        if evidence.source_id == RECEIVER_POSITION:
            alpha = 0.00003
        elif evidence.source_id == RECEIVER_VELOCITY:
            alpha = 0.04
        elif evidence.source_id == DUAL_ANTENNA_YAW:
            alpha = 0.03
        elif evidence.source_id == RAW_DOPPLER_VELOCITY:
            alpha = 0.35
        else:
            alpha = 0.18
        scale = 1.0 + alpha * delta * delta
        if normalized > cfg.strong_normalized:
            scale = max(scale, 1.0 + (alpha * 1.6) * delta * delta)
            reasons.append("oim_strong_normalized_innovation")
        elif normalized > cfg.moderate_normalized:
            scale = max(scale, 1.0 + (alpha * 1.2) * delta * delta)
            reasons.append("oim_moderate_normalized_innovation")
        else:
            reasons.append("oim_mild_normalized_innovation")
    if evidence.source_id == RAW_DOPPLER_VELOCITY and normalized > 2.0:
        reasons.append("oim_raw_doppler_innovation_suspicious")

    rolling_median = 0.0
    rolling_mad = 0.0
    anomaly = 0.0
    if cfg.enable_rolling_innovation_baseline and rolling_history:
        rolling_median = float(median(float(value) for value in rolling_history))
        deviations = [abs(float(value) - rolling_median) for value in rolling_history]
        rolling_mad = max(cfg.rolling_mad_floor, float(median(deviations)))
        anomaly = max(0.0, (normalized - rolling_median) / rolling_mad)
        if anomaly > 3.0:
            reasons.append("oim_solver_visible_rolling_anomaly")

    scale = _cap(scale, evidence.source_id, cfg)
    return {
        **metrics,
        "oim_R_scale": scale,
        "rolling_normalized_median": rolling_median,
        "rolling_normalized_mad": rolling_mad,
        "relative_anomaly_score": anomaly,
        "reject": bool(cfg.reject_extreme and normalized > 10.0),
        "reason_codes": reasons or ["nominal"],
    }


def combine_n6b_source_weight(
    metadata: SourceMetadata,
    evidence: InnovationCovarianceInput,
    config: N6BPolicyConfig | None = None,
    *,
    rolling_history: Sequence[float] = (),
) -> N6BPolicyResult:
    cfg = config or N6BPolicyConfig()
    if cfg.mode == "off" or not cfg.per_source_enabled.get(metadata.source_id, True):
        return N6BPolicyResult(source_id=metadata.source_id, source_cap=source_cap(metadata.source_id, cfg))
    lsim = {"lsim_R_scale": 1.0, "reject": False, "reason_codes": []}
    oim = {
        "oim_R_scale": 1.0,
        "normalized_innovation": 0.0,
        "nis": 0.0,
        "dof": 0,
        "innovation_cov_trace": 0.0,
        "used_innovation_covariance": False,
        "rolling_normalized_median": 0.0,
        "rolling_normalized_mad": 0.0,
        "relative_anomaly_score": 0.0,
        "reject": False,
        "reason_codes": [],
    }
    if cfg.mode in {"lsim_only", "lsim_oim"} and cfg.per_source_lsim_enabled.get(metadata.source_id, True):
        lsim = compute_lsim_n6b(metadata, cfg)
    if cfg.mode in {"oim_only", "lsim_oim"} and cfg.per_source_oim_enabled.get(metadata.source_id, True):
        oim = compute_oim_n6b(evidence, cfg, rolling_history=rolling_history)
    combined = _cap(max(float(lsim["lsim_R_scale"]), float(oim["oim_R_scale"])), metadata.source_id, cfg)
    reasons = tuple(
        reason
        for reason in [*lsim.get("reason_codes", []), *oim.get("reason_codes", [])]
        if reason and reason != "nominal"
    ) or ("nominal",)
    return N6BPolicyResult(
        source_id=metadata.source_id,
        lsim_R_scale=float(lsim["lsim_R_scale"]),
        oim_R_scale=float(oim["oim_R_scale"]),
        combined_R_scale=combined,
        normalized_innovation=float(oim["normalized_innovation"]),
        nis=float(oim["nis"]),
        dof=int(oim["dof"]),
        innovation_cov_trace=float(oim["innovation_cov_trace"]),
        used_innovation_covariance=bool(oim["used_innovation_covariance"]),
        source_cap=source_cap(metadata.source_id, cfg),
        rolling_normalized_median=float(oim["rolling_normalized_median"]),
        rolling_normalized_mad=float(oim["rolling_normalized_mad"]),
        relative_anomaly_score=float(oim["relative_anomaly_score"]),
        reject=bool(lsim["reject"]) or bool(oim["reject"]),
        reason_codes=reasons,
    )
