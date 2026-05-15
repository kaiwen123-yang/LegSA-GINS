from scripts.audit_n8k3_duplicate_semantic_plots import make_toy_n8k3_root
from scripts.audit_n8k3_no_degradation_matrix_run import _audit

# 中文说明：N8K3 不运行退化矩阵。


def test_n8k3_no_degradation_matrix_run_toy(tmp_path):
    root = tmp_path / "n8k3"
    make_toy_n8k3_root(root)
    _audit(root)
