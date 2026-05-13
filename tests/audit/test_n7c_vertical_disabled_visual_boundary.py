"""N7C1 vertical-disabled boundary audit test.

中文说明：缺少 vertical-disabled evidence 时 N7C1 不能 visual pass。
"""

from scripts.audit_n7c_vertical_disabled_visual_boundary import main


def test_n7c_vertical_disabled_visual_boundary_audit():
    assert main() == 0
