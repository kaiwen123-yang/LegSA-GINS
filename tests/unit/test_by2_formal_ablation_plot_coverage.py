from pathlib import Path

from legsa_gins.reporting.by2_formal_ablation_metrics import build_formal_ablation_metrics
from legsa_gins.reporting.by2_formal_ablation_plot_catalog import build_plot_catalog
from legsa_gins.reporting.by2_formal_ablation_plot_coverage import build_plot_coverage
from legsa_gins.reporting.by2_formal_ablation_plot_generator import generate_ablation_plots
from legsa_gins.reporting.by2_formal_ablation_spec import build_formal_ablation_matrix, build_formal_ablation_spec
from scripts.audit_n8j_feedback_final_validation import make_toy_n8j_root

# 中文说明：coverage toy 测试要求不适用项也有占位图。


def test_by2_formal_ablation_plot_coverage_complete(tmp_path: Path):
    n8j = tmp_path / "n8j"
    make_toy_n8j_root(n8j)
    matrix = build_formal_ablation_matrix(build_formal_ablation_spec())
    metrics = build_formal_ablation_metrics(matrix, n8j)
    catalog = build_plot_catalog(matrix)
    generation = generate_ablation_plots(catalog, matrix, metrics, tmp_path / "figures")
    coverage = build_plot_coverage(catalog, generation, tmp_path / "figures")
    assert coverage["all_required_categories_complete"] is True
    assert coverage["missing_count"] == 0
