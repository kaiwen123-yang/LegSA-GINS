"""Yaw frame adapter for BY2 lateral dual-antenna baseline."""

from __future__ import annotations

from .wrapped_angle_utils import wrap360_deg, yaw_error_deg

FIXED_LATERAL_TO_BODY_OFFSET_DEG = 90.0


def baseline_heading_to_body_yaw_ned_deg(baseline_heading_ned_deg: float) -> float:
    """Convert GNSS1->GNSS2 lateral baseline heading to body yaw.

    中文说明：BY2 中 GNSS1 是右侧天线，GNSS2 是左侧天线，GNSS1->GNSS2
    是机体系 +Y_left 横向基线。body forward yaw 采用固定 +90 deg 物理转换。
    该转换不能用 trace RMSE、per-case offset 或 method-specific tuning 选择。
    """

    return wrap360_deg(baseline_heading_ned_deg + FIXED_LATERAL_TO_BODY_OFFSET_DEG)


def wrap_safe_body_yaw_residual_deg(method_body_yaw_deg: float, reference_body_yaw_deg: float) -> float:
    return yaw_error_deg(method_body_yaw_deg, reference_body_yaw_deg)
