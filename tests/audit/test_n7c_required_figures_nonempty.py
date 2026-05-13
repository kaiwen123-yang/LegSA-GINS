"""N7C1 required figure coverage audit test.

中文说明：确认 mandatory figure coverage gate 能拦截空图和缺数据图。
"""

from scripts.audit_n7c_required_figures_nonempty import main


def test_n7c_required_figures_nonempty_audit():
    assert main() == 0
