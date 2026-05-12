from scripts.audit_n6b1_required_figures_nonempty import main


def test_n6b1_required_figures_nonempty_audit():
    # 中文说明：mandatory figure coverage gate 必须拒绝空图和数据不足的图。
    assert main() == 0
