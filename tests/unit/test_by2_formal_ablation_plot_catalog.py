from legsa_gins.reporting.by2_formal_ablation_plot_catalog import PLOT_CATEGORIES, build_plot_catalog
from legsa_gins.reporting.by2_formal_ablation_spec import build_formal_ablation_matrix, build_formal_ablation_spec

# 中文说明：图像目录测试确保 14 类必画项存在。


def test_by2_formal_ablation_plot_catalog_has_14_categories():
    catalog = build_plot_catalog(build_formal_ablation_matrix(build_formal_ablation_spec()))
    assert len(PLOT_CATEGORIES) == 14
    assert catalog["category_count"] == 14
    assert catalog["variant_count"] == 30
    assert catalog["png_figure_count_expected"] > 0
