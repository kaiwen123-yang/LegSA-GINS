import json

from scripts.audit_n8k3_duplicate_semantic_plots import make_toy_n8k3_root
from scripts.audit_n8k3_real_plot_semantic_distinction import REQUIRED_FIXES, _audit

# 中文说明：四类重点图必须记录不同 semantic fix。


def test_n8k3_real_plot_semantic_distinction_toy(tmp_path):
    root = tmp_path / "n8k3"
    make_toy_n8k3_root(root)
    path = root / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json"
    report = json.loads(path.read_text())
    report["fixed_entries"] = [{"semantic_fix": item} for item in REQUIRED_FIXES]
    path.write_text(json.dumps(report), encoding="utf-8")
    _audit(root)
