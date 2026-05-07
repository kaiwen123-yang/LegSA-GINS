"""Explicit frame names and tagged vector contracts.

中文说明：frame 模块固定 Go2 FLU、NED/ENU/ECEF/BLH、qbn/qeb 与 yaw 约定，防止 Go2 body/odom/map/navigation frame 混用和双重 FLU->FRD。
"""

from dataclasses import dataclass
from enum import Enum


class FrameName(str, Enum):
    GO2_BODY_FLU = "GO2_BODY_FLU"
    IMU_FRD_COMPATIBLE = "IMU_FRD_COMPATIBLE"
    NED = "NED"
    ENU = "ENU"
    ECEF = "ECEF"
    BLH = "BLH"
    BODY = "BODY"
    ODOM = "ODOM"
    MAP = "MAP"


@dataclass(frozen=True)
class FrameTaggedVector:
    values: tuple[float, float, float]
    frame: str
    source: str = ""


GO2_FLU_DESCRIPTION = "Go2 body/IMU frame is FLU: X forward, Y left, Z up."

FINAL_V23_IMU_ASSUMPTION = (
    "final_v23-style IMU stream is treated as FRD-compatible unless explicitly "
    "declared otherwise."
)
