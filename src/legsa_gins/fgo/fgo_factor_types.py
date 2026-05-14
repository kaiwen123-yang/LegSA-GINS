"""Factor contract types for N8A."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FGOFactorContract:
    """中文说明：factor 合同只描述残差和状态块，不代表 truth claim。"""

    factor_name: str
    source: str
    active_default: bool
    diagnostic_only: bool
    residual_dimension: int
    state_blocks_touched: tuple[str, ...]
    measurement_source: str
    covariance_policy: str
    residual_formula: str = ""
    truth_claim: bool = False
    trace_input: bool = False
    finalv23_input: bool = False
    no_feedback: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state_blocks_touched"] = list(self.state_blocks_touched)
        return data


@dataclass(frozen=True)
class LinearFactor:
    """中文说明：toy linear factor 用于 foundation solver 单元测试。"""

    state_index: int
    dimension: int
    weight: float = 1.0
    name: str = "linear_factor"


@dataclass(frozen=True)
class RawDopplerVelocityFactorRow:
    """中文说明：Raw Doppler FGO 因子表行，直接约束速度状态块。"""

    state_index: int
    time: float
    vn_mps: float
    ve_mps: float
    vd_mps: float
    std_vn_mps: float = 0.2
    std_ve_mps: float = 0.2
    std_vd_mps: float = 0.2
    active: bool = True
    factor_type: str = "RawDopplerVelocityFactor"

    def measurement(self) -> tuple[float, float, float]:
        return (self.vn_mps, self.ve_mps, self.vd_mps)

    def std(self) -> tuple[float, float, float]:
        return (self.std_vn_mps, self.std_ve_mps, self.std_vd_mps)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
