"""Shared N5A raw Doppler types.

中文说明：这些 dataclass 只描述卫星级 Doppler 观测和由成熟 provider 支撑的速度因子；
不读取 trace，不读取 final_v23 输出，也不承载 paper performance claim。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


LIGHT_SPEED_MPS = 299_792_458.0


@dataclass(frozen=True)
class RawDopplerMeasurement:
    """卫星级 RAWX Doppler 观测，不是 NAV-PVT velocity。"""

    time: float
    rcv_tow: float
    week: int
    gnss_id: int
    sv_id: int
    sig_id: int
    freq_id: int
    pr_mes: float
    cp_mes: float
    do_mes_hz: float
    cno: float
    do_stdev: int
    trk_stat: int
    wavelength_m: float | None
    source_file: str = ""

    @property
    def observed_range_rate_mps(self) -> float | None:
        if self.wavelength_m is None:
            return None
        # 中文说明：u-blox doMes 是 Doppler Hz；负号按常见 GNSS range-rate 约定转换。
        return -self.do_mes_hz * self.wavelength_m


@dataclass(frozen=True)
class SatelliteState:
    """成熟 satellite-state provider 输出的卫星 ECEF 状态。"""

    time: float
    gnss_id: int
    sv_id: int
    pos_ecef_m: tuple[float, float, float]
    vel_ecef_mps: tuple[float, float, float]
    clock_drift_mps: float = 0.0


@dataclass(frozen=True)
class ReceiverApproxState:
    """Doppler LS 所需的接收机近似 ECEF/LLH 状态。"""

    lat_rad: float
    lon_rad: float
    pos_ecef_m: tuple[float, float, float]


@dataclass
class DopplerVelocitySolution:
    """raw-Doppler-derived auxiliary velocity factor."""

    time: float
    vn: float
    ve: float
    vd: float
    std_vn: float
    std_ve: float
    std_vd: float
    sat_count: int
    gdop_like: float
    provider_status: str
    residual_rms_mps: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReadinessDecision:
    """N5A activation gate output."""

    activation_allowed: bool
    solver_enabled: bool
    blocking_issue: str
    recommended_next_stage: str
    blocker_reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "activation_allowed": self.activation_allowed,
            "raw_doppler_solver_activation_allowed": self.activation_allowed,
            "solver_enabled": self.solver_enabled,
            "blocking_issue": self.blocking_issue,
            "recommended_next_stage": self.recommended_next_stage,
            "blocker_reasons": self.blocker_reasons,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        }
