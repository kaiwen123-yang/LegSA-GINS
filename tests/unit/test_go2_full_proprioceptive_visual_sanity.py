"""Unit tests for N7C5A visual sanity checks.

中文说明：测试 N7C5A 图像 sanity gate。
"""

from scripts.audit_n7c5a_go2_full_proprioceptive_visual_review import _prepare_n7c5_root
from legsa_gins.go2_prior.go2_full_proprioceptive_plot_coverage import build_n7c5a_plot_data_coverage
from legsa_gins.go2_prior.go2_full_proprioceptive_visual_loader import load_n7c5_visual_inputs
from legsa_gins.go2_prior.go2_full_proprioceptive_visual_sanity import build_n7c5a_visual_sanity


def test_n7c5a_visual_sanity_passes_toy(tmp_path):
    n7c5 = _prepare_n7c5_root(tmp_path)
    inputs = load_n7c5_visual_inputs(n7c5)
    figures = {"figure_count_total": 18, "required_figures_generated": True, "required_figures_nonempty": True}
    inputs["figure_manifest"] = figures
    coverage = build_n7c5a_plot_data_coverage(inputs)
    sanity = build_n7c5a_visual_sanity(inputs, figures, coverage)
    assert sanity["visual_blocker"] is False
    assert sanity["checks"]["foot_kinematic_velocity_has_finite_series"] is True
