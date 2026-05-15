from scripts.audit_n8k3_duplicate_semantic_plots import audit_runtime, make_toy_n8k3_root

# 中文说明：主审计 toy 覆盖 N8K3 duplicate semantic reports。


def test_n8k3_duplicate_semantic_plots_toy(tmp_path):
    root = tmp_path / "n8k3"
    make_toy_n8k3_root(root)
    audit_runtime(root)
