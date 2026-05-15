from legsa_gins.reporting.by2_placeholder_plot_detector import detect_placeholder_plots
from legsa_gins.reporting.by2_real_plot_coverage import build_real_plot_coverage
from legsa_gins.reporting.by2_real_plot_data_loader import load_real_plot_data
from legsa_gins.reporting.by2_real_plot_decision import build_real_plot_decision
from legsa_gins.reporting.by2_real_plot_materializer import materialize_real_plots
from tests.unit.test_by2_real_plot_data_loader import make_n8k2_toy_inputs

# 中文说明：集成 toy 覆盖 N8K2 load-materialize-detect-coverage-decision 全链路。


def test_n8k2_by2_formal_ablation_real_plot_fix_toy(tmp_path):
    n8k, n8j = make_n8k2_toy_inputs(tmp_path)
    bundle = load_real_plot_data(n8k, n8j)
    materialization = materialize_real_plots(n8k_root=n8k, data_bundle=bundle, figure_output_dir=tmp_path / "fixed", case_review_dir=tmp_path / "case", summary_dir=tmp_path / "summary")
    placeholder = detect_placeholder_plots(n8k_root=n8k, original_figure_root=tmp_path / "old", fixed_figure_root=tmp_path / "fixed")
    coverage = build_real_plot_coverage(n8k_root=n8k, materialization=materialization, placeholder_report=placeholder, data_report=bundle["report"])
    decision = build_real_plot_decision(coverage)
    assert decision["status"] == "BY2_formal_ablation_real_plot_fix_complete"
