from scripts.audit_n8k2_plot_data_rows import _audit
from scripts.audit_n8k2_by2_formal_ablation_real_plot_fix import make_toy_n8k2_root

# 中文说明：数据行审计要求没有 unresolved missing data。


def test_n8k2_plot_data_rows_toy(tmp_path):
    root = tmp_path / "n8k2"
    make_toy_n8k2_root(root)
    _audit(root)
