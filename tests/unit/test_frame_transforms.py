"""中文说明：unit 测试验证小模块约定和边界，不做 numerical performance claim。
"""

from legsa_gins.frames.transforms import enu_to_ned, flu_to_frd, frd_to_flu, ned_to_enu


def test_body_frame_transforms():
    assert flu_to_frd((1, 2, 3)) == (1, -2, -3)
    assert frd_to_flu((1, -2, -3)) == (1, 2, 3)


def test_navigation_frame_transforms():
    assert enu_to_ned((10, 20, 5)) == (20, 10, -5)
    assert ned_to_enu((20, 10, -5)) == (10, 20, 5)
