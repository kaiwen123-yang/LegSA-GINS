from pathlib import Path

from legsa_gins.reporting.by2_formal_ablation_case_review import build_case_reviews
from legsa_gins.reporting.by2_formal_ablation_metrics import build_formal_ablation_metrics
from legsa_gins.reporting.by2_formal_ablation_spec import build_formal_ablation_matrix, build_formal_ablation_spec
from scripts.audit_n8j_feedback_final_validation import make_toy_n8j_root

# 中文说明：case review 测试只检查审计文档数量和边界。


def test_by2_formal_ablation_case_review_count(tmp_path: Path):
    n8j = tmp_path / "n8j"
    make_toy_n8j_root(n8j)
    matrix = build_formal_ablation_matrix(build_formal_ablation_spec())
    metrics = build_formal_ablation_metrics(matrix, n8j)
    summary, index = build_case_reviews(matrix, metrics, tmp_path / "case", tmp_path / "summary")
    assert summary["review_count"] == 30
    assert index["case_review_count"] == 30
