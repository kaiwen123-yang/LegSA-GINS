from legsa_gins.reporting.by2_placeholder_plot_detector import detect_placeholder_plots
from legsa_gins.reporting.by2_real_plot_data_loader import load_real_plot_data
from legsa_gins.reporting.by2_real_plot_materializer import materialize_real_plots
from tests.unit.test_by2_real_plot_data_loader import make_n8k2_toy_inputs

# 中文说明：detector 应能发现旧 N8K 模板图，并确认 N8K2 applicable placeholder 清零。


def test_placeholder_detector_counts_fixed_zero(tmp_path):
    n8k, n8j = make_n8k2_toy_inputs(tmp_path)
    bundle = load_real_plot_data(n8k, n8j)
    materialize_real_plots(n8k_root=n8k, data_bundle=bundle, figure_output_dir=tmp_path / "fixed", case_review_dir=tmp_path / "case", summary_dir=tmp_path / "summary")
    report = detect_placeholder_plots(n8k_root=n8k, original_figure_root=tmp_path / "missing_original", fixed_figure_root=tmp_path / "fixed")
    assert report["fixed_applicable_placeholder_count"] == 0
    assert report["original_applicable_placeholder_count"] > 0
