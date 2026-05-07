from legsa_gins.frames.transforms import wrap_angle_deg, wrap_heading_deg
from legsa_gins.frames.yaw import heading_to_yaw_math_deg, yaw_math_to_heading_deg


def test_yaw_math_to_heading_examples():
    assert yaw_math_to_heading_deg(0.0) == 90.0
    assert yaw_math_to_heading_deg(90.0) == 0.0


def test_heading_to_yaw_math_examples():
    assert heading_to_yaw_math_deg(0.0) == 90.0
    assert heading_to_yaw_math_deg(90.0) == 0.0


def test_angle_wrapping():
    assert wrap_angle_deg(180.0) == -180.0
    assert wrap_angle_deg(540.0) == -180.0
    assert wrap_heading_deg(-90.0) == 270.0
    assert wrap_heading_deg(450.0) == 90.0
