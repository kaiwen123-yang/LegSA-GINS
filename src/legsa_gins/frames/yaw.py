"""Yaw/heading convention helpers.

yaw_math is a mathematical angle in an ENU-style convention, counter-clockwise
positive from East. yaw_heading is a navigation heading, clockwise positive from
North.

The real final_v23 yaw convention still requires an oracle check after real
outputs are connected. N2 only provides explicit, testable convention utilities.
"""

from legsa_gins.frames.transforms import wrap_angle_deg, wrap_heading_deg


def yaw_math_to_heading_deg(yaw_math_deg: float) -> float:
    return wrap_heading_deg(90.0 - yaw_math_deg)


def heading_to_yaw_math_deg(heading_deg: float) -> float:
    return wrap_angle_deg(90.0 - heading_deg)
