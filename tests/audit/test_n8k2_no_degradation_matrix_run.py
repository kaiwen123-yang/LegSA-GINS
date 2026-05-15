from scripts.audit_n8k2_no_degradation_matrix_run import _audit
from scripts.audit_n8k2_by2_formal_ablation_real_plot_fix import make_toy_n8k2_root

# 中文说明：N8K2 不运行退化矩阵。


def test_n8k2_no_degradation_matrix_run_toy(tmp_path):
    root = tmp_path / "n8k2"
    make_toy_n8k2_root(root)
    _audit(root)
