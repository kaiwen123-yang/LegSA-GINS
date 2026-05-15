import json

from scripts.audit_n8k_by2_formal_ablation_plot_audit import make_toy_n8k_root

# 中文说明：审计 toy 确认 14 类图像类别完整。


def test_n8k_ablation_required_plot_categories_toy(tmp_path):
    root = tmp_path / "n8k"
    make_toy_n8k_root(root)
    coverage = json.loads((root / "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json").read_text())
    assert coverage["required_category_count"] == 14
    assert coverage["missing_count"] == 0
