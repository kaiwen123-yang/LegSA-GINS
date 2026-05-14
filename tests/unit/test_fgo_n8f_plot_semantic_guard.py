"""Unit tests for N8F1 plot semantic guard.

中文说明：检查图像语义命名不包含 truth/performance 越界宣称。
"""

from legsa_gins.fgo.fgo_n8f_plot_semantic_guard import build_n8f_plot_semantic_guard


def test_semantic_guard_allows_declared_namespaces() -> None:
    report = build_n8f_plot_semantic_guard(
        figure_manifest={"generated_figures": [{"figure_name": "a.png"}]},
        semantic_labels=[{"figure_name": "a.png", "title": "residual proxy", "metric_namespace": "residual_proxy"}],
    )
    assert report["semantic_guard_passed"] is True

