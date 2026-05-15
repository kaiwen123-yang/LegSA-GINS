from scripts.audit_n8k2_plot_outputs_under_by2_audit_root import _audit
from scripts.audit_n8k2_by2_formal_ablation_real_plot_fix import make_toy_n8k2_root

# 中文说明：输出根审计禁止 tracked 报告记录本地绝对路径。


def test_n8k2_plot_outputs_under_by2_audit_root_toy(tmp_path):
    root = tmp_path / "n8k2"
    make_toy_n8k2_root(root)
    _audit(root)
