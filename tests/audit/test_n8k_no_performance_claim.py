import json

from scripts.audit_n8k_by2_formal_ablation_plot_audit import REQUIRED_REPORTS, make_toy_n8k_root

# 中文说明：审计 toy 确认所有 N8K 报告无论文性能宣称。


def test_n8k_no_performance_claim_toy(tmp_path):
    root = tmp_path / "n8k"
    make_toy_n8k_root(root)
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text())
        assert payload.get("paper_performance_claim") is False
