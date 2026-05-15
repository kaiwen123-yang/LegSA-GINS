from scripts.audit_n8k_by2_formal_ablation_plot_audit import audit_runtime, make_toy_n8k_root

# 中文说明：主审计 toy 覆盖 N8K 报告合同。


def test_n8k_by2_formal_ablation_plot_audit_toy(tmp_path):
    root = tmp_path / "n8k"
    make_toy_n8k_root(root)
    audit_runtime(root)
