from scripts.audit_n8k3_duplicate_semantic_plots import make_toy_n8k3_root
from scripts.audit_n8k3_no_algorithm_change import _audit

# 中文说明：N8K3 不改算法。


def test_n8k3_no_algorithm_change_toy(tmp_path):
    root = tmp_path / "n8k3"
    make_toy_n8k3_root(root)
    _audit(root)
