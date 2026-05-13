"""N7C1 visual validation audit test.

中文说明：审计使用 synthetic toy 数据，不读取真实 runtime 输出。
"""

from scripts.audit_n7c1_go2_horizontal_velocity_visual_validation import main


def test_n7c1_go2_horizontal_velocity_visual_validation_audit():
    assert main() == 0
