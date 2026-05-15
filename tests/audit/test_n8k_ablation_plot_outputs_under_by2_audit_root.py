import json

from scripts.audit_n8k_by2_formal_ablation_plot_audit import make_toy_n8k_root

# 中文说明：审计 toy 确认图像输出归属 BY2 绘图审计根。


def test_n8k_ablation_plot_outputs_under_by2_audit_root_toy(tmp_path):
    root = tmp_path / "n8k"
    make_toy_n8k_root(root)
    coverage = json.loads((root / "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json").read_text())
    assert coverage["all_required_categories_complete"] is True
