from legsa_gins.reporting.by2_real_plot_data_loader import load_real_plot_data
from legsa_gins.reporting.by2_real_plot_materializer import materialize_real_plots
from tests.unit.test_by2_real_plot_data_loader import make_n8k2_toy_inputs

# 中文说明：materializer 必须写出真实图像并保留 N8K2 输出 role。


def test_materializer_generates_figures(tmp_path):
    n8k, n8j = make_n8k2_toy_inputs(tmp_path)
    bundle = load_real_plot_data(n8k, n8j)
    report = materialize_real_plots(n8k_root=n8k, data_bundle=bundle, figure_output_dir=tmp_path / "fig", case_review_dir=tmp_path / "case", summary_dir=tmp_path / "summary")
    assert report["figures_generated"] > 0
    assert report["real_data_figures"] > 0
    assert report["blockers"] == []
