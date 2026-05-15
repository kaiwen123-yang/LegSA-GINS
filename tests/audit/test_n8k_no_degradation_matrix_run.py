import json

from scripts.audit_n8k_by2_formal_ablation_plot_audit import make_toy_n8k_root

# 中文说明：审计 toy 确认 N8K 未运行全量退化矩阵。


def test_n8k_no_degradation_matrix_run_toy(tmp_path):
    root = tmp_path / "n8k"
    make_toy_n8k_root(root)
    plan = json.loads((root / "N8K_N9B_DEGRADATION_PLAN_REPORT.json").read_text())
    assert plan["degradation_matrix_run"] is False
