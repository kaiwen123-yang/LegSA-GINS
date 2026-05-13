"""Audit test for N7C2 runner.

中文说明：复用 synthetic runtime 检查 runner 产物，不写 tracked runtime 文件。
"""

from scripts.audit_n7c2_go2_horizontal_velocity_jacobian_visual_audit import _toy_run


def test_n7c2_go2_horizontal_velocity_jacobian_visual_audit():
    _toy_run()
