"""中文说明：双天线横向安装测试只验证 candidate wrap，不做 formal selection。"""

from legsa_gins.datasets.by2.dual_antenna_heading_convention import (
    apply_transverse_heading_offset,
    candidate_heading_offsets,
)


def test_heading_plus_minus_90_wraps():
    assert apply_transverse_heading_offset(350.0, 90.0) == 80.0
    assert apply_transverse_heading_offset(10.0, -90.0) == 280.0
    assert [item["heading_offset_mode"] for item in candidate_heading_offsets()] == [
        "no_offset",
        "plus90",
        "minus90",
    ]

