"""Audit test for N7C2 overlap explanation.

中文说明：在 pytest 中调用脚本级 overlap explanation 审计。
"""

from scripts.audit_n7c_visual_overlap_explained import main


def test_n7c_visual_overlap_explained():
    assert main() == 0
