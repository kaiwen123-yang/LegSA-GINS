from scripts.audit_n8k3_duplicate_semantic_plots import make_toy_n8k3_root
from scripts.audit_n8k3_no_same_category_exact_duplicates import _audit

# 中文说明：同类 exact duplicate 清零审计。


def test_n8k3_no_same_category_exact_duplicates_toy(tmp_path):
    root = tmp_path / "n8k3"
    make_toy_n8k3_root(root)
    _audit(root)
