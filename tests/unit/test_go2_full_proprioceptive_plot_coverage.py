"""Unit tests for N7C5A plot coverage.

中文说明：测试 N7C5A 图像覆盖统计。
"""

from scripts.audit_n7c5a_go2_full_proprioceptive_visual_review import _prepare_n7c5_root
from legsa_gins.go2_prior.go2_full_proprioceptive_plot_coverage import build_n7c5a_plot_data_coverage
from legsa_gins.go2_prior.go2_full_proprioceptive_visual_loader import load_n7c5_visual_inputs


def test_n7c5a_plot_coverage_counts_toy_rows(tmp_path):
    n7c5 = _prepare_n7c5_root(tmp_path)
    inputs = load_n7c5_visual_inputs(n7c5)
    inputs["figure_manifest"] = {"figure_count_total": 18, "required_figures_generated": True, "required_figures_nonempty": True}
    coverage = build_n7c5a_plot_data_coverage(inputs)
    assert coverage["contact_finite_rows"] > 0
    assert coverage["foot_kinematic_finite_rows"] > 0
    assert coverage["ranking_candidate_count"] == 3
