from scripts.audit_n8k_by2_formal_ablation_plot_audit import audit_runtime, make_toy_n8k_root

# 中文说明：正式消融完整性 toy 不允许缺 variant。


def test_n8k_formal_ablation_complete_toy(tmp_path):
    root = tmp_path / "n8k"
    make_toy_n8k_root(root)
    audit_runtime(root)
