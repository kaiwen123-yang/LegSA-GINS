"""Yaw/heading convention helpers.
中文说明：frame 模块固定 Go2 FLU、NED/ENU/ECEF/BLH、qbn/qeb 与 yaw 约定，防止 Go2 body/odom/map/navigation frame 混用和双重 FLU->FRD。

yaw_math is a mathematical angle in an ENU-style convention, counter-clockwise
positive from East. yaw_heading is a navigation heading, clockwise positive from
North.

The real final_v23 yaw convention still requires an oracle check after real
outputs are connected. N2 only provides explicit, testable convention utilities.
"""

from legsa_gins.frames.transforms import wrap_angle_deg, wrap_heading_deg


def yaw_math_to_heading_deg(yaw_math_deg: float) -> float:
    # 中文说明：数学 yaw 与航向 heading 的转换只服务约定统一，不做 trace tuning。
    # Yaw/heading conversion is convention handling only, not trace tuning.
    return wrap_heading_deg(90.0 - yaw_math_deg)


def heading_to_yaw_math_deg(heading_deg: float) -> float:
    return wrap_angle_deg(90.0 - heading_deg)
