import json

from scripts.audit_n8k_by2_formal_ablation_plot_audit import make_toy_n8k_root

# 中文说明：审计 toy 确认 N8K 不改算法或 feedback policy。


def test_n8k_no_algorithm_change_toy(tmp_path):
    root = tmp_path / "n8k"
    make_toy_n8k_root(root)
    matrix = json.loads((root / "N8K_BY2_FORMAL_ABLATION_MATRIX.json").read_text())
    assert matrix["algorithm_changes"] is False
    assert matrix["feedback_policy_changed"] is False
