from pathlib import Path

from legsa_gins.reporting.by2_formal_ablation_metrics import build_formal_ablation_metrics
from legsa_gins.reporting.by2_formal_ablation_spec import build_formal_ablation_matrix, build_formal_ablation_spec
from scripts.audit_n8j_feedback_final_validation import make_toy_n8j_root

# 中文说明：指标测试只验证工程审计 namespace 和表格字段。


def test_by2_formal_ablation_metrics_builds_rows(tmp_path: Path):
    n8j = tmp_path / "n8j"
    make_toy_n8j_root(n8j)
    matrix = build_formal_ablation_matrix(build_formal_ablation_spec({"n8j": "role"}))
    report = build_formal_ablation_metrics(matrix, n8j)
    assert report["variant_count"] == 30
    assert report["paper_performance_claim"] is False
    assert report["metrics"][0]["metric_namespace"] == "BY2_formal_ablation_engineering_delta"
