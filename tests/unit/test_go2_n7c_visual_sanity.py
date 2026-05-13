"""N7C1 visual sanity unit tests.

中文说明：使用 synthetic runtime 图像链路确认 sanity 报告能通过边界检查。
"""

from scripts.audit_n7c1_go2_horizontal_velocity_visual_validation import _prepare_n7c_runtime
from legsa_gins.go2_prior.go2_n7c_plot_coverage import summarize_n7c1_plot_coverage
from legsa_gins.go2_prior.go2_n7c_visual_loader import load_n7c1_visual_inputs
from legsa_gins.go2_prior.go2_n7c_visual_plots import generate_n7c1_visual_figures
from legsa_gins.go2_prior.go2_n7c_visual_sanity import build_n7c1_visual_sanity_report


def test_n7c1_visual_sanity_passes_for_toy_runtime(tmp_path):
    n7c, n7b5, n5b, n6b, dual = _prepare_n7c_runtime(tmp_path)
    inputs = load_n7c1_visual_inputs(n7c_root=n7c, n7b5_root=n7b5, n5b_root=n5b, n6b_root=n6b, dual_root=dual)
    figure_manifest = generate_n7c1_visual_figures(visual_inputs=inputs, figure_output_dir=tmp_path / "figs")
    coverage = summarize_n7c1_plot_coverage(figure_manifest["coverage"])
    sanity = build_n7c1_visual_sanity_report(
        visual_inputs=inputs,
        figure_manifest=figure_manifest,
        coverage_report=coverage,
    )
    assert sanity["visual_sanity_passed"] is True
    assert sanity["go2_horizontal_prior_update_count_matches_report"] is True
    assert sanity["vertical_velocity_disabled_confirmed"] is True
    assert sanity["paper_performance_claim"] is False
