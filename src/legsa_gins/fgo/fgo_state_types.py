"""State containers for the N8A no-feedback FGO foundation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FGOState:
    """中文说明：单个 FGO 状态节点；只做离线诊断，不回写 EKF。"""

    index: int
    time: float
    lat_deg: float = 0.0
    lon_deg: float = 0.0
    height_m: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    vn_mps: float = 0.0
    ve_mps: float = 0.0
    vd_mps: float = 0.0

    def vector(self) -> list[float]:
        return [
            self.lat_deg,
            self.lon_deg,
            self.height_m,
            self.roll_deg,
            self.pitch_deg,
            self.yaw_deg,
            self.vn_mps,
            self.ve_mps,
            self.vd_mps,
        ]


@dataclass(frozen=True)
class FGOStateDataset:
    states: list[FGOState]
    role: str = "diagnostic_state_nodes"

    @property
    def state_count(self) -> int:
        return len(self.states)

    def to_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "index": state.index,
                "time": state.time,
                "lat_deg": state.lat_deg,
                "lon_deg": state.lon_deg,
                "height_m": state.height_m,
                "roll_deg": state.roll_deg,
                "pitch_deg": state.pitch_deg,
                "yaw_deg": state.yaw_deg,
                "vn_mps": state.vn_mps,
                "ve_mps": state.ve_mps,
                "vd_mps": state.vd_mps,
            }
            for state in self.states
        ]
