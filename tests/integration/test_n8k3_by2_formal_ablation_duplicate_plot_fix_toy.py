from tests.unit.test_by2_duplicate_semantic_plot_detector import _make_duplicate_figures

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.by2_duplicate_semantic_plot_detector import materialize_n8k3_duplicate_fix

# 中文说明：N8K3 toy 集成覆盖 duplicate scan/fix/decision。


def test_n8k3_by2_formal_ablation_duplicate_plot_fix_toy(tmp_path):
    n8k2_root = tmp_path / "n8k2"
    fig = tmp_path / "n8k2_fig"
    _make_duplicate_figures(fig)
    write_json(n8k2_root / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json", {"data_sources": {"A": "derived_from_n8k_metrics_and_baseline_nav"}, "feedback_rows_per_variant": {"A": 4}, "paper_performance_claim": False})
    write_json(n8k2_root / "N8K2_REAL_PLOT_MATERIALIZATION_REPORT.json", {"generated": [], "paper_performance_claim": False})
    result = materialize_n8k3_duplicate_fix(n8k2_root=n8k2_root, n8k2_figure_root=fig, output_dir=tmp_path / "out", figure_output_dir=tmp_path / "fixed", case_review_dir=tmp_path / "case", summary_dir=tmp_path / "summary")
    assert result["decision"]["same_category_exact_duplicate_remaining"] == 0
