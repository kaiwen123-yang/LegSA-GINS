from scripts.audit_n8k2_by2_formal_ablation_real_plot_fix import audit_runtime, make_toy_n8k2_root

# 中文说明：主审计 toy 覆盖 N8K2 真实绘图修复合同。


def test_n8k2_by2_formal_ablation_real_plot_fix_toy(tmp_path):
    root = tmp_path / "n8k2"
    make_toy_n8k2_root(root)
    audit_runtime(root)
