from scripts.audit_n8k3_data_source_labels import _audit
from scripts.audit_n8k3_duplicate_semantic_plots import make_toy_n8k3_root

# 中文说明：derived/surrogate 标签必须存在。


def test_n8k3_data_source_labels_toy(tmp_path):
    root = tmp_path / "n8k3"
    make_toy_n8k3_root(root)
    _audit(root)
