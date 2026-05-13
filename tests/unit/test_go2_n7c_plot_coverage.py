"""N7C1 plot coverage unit tests.

中文说明：验证 plotted-data coverage 能拦截空图、短时间轴和缺少必需系列。
"""

from legsa_gins.go2_prior.go2_n7c_plot_coverage import (
    inspect_n7c1_plot_source_data,
    summarize_n7c1_plot_coverage,
)


def test_n7c1_clean_coverage_requires_rows_time_and_series(tmp_path):
    fig = tmp_path / "fig.png"
    fig.write_bytes(b"nonempty")
    bad = inspect_n7c1_plot_source_data(
        "01_clean_validation/clean_horizontal_error_no_go2_vs_go2_horizontal.png",
        {
            "figure_path": str(fig),
            "figure_category": "clean",
            "series": [{"label": "no_go2", "x": [0, 1], "y": [0.1, 0.2]}],
            "min_rows": 1000,
            "min_series": 2,
            "min_x_range": 200.0,
        },
    )
    assert bad.empty_plot_suspect
    assert "clean_required_series_missing" in bad.reason_codes
    valid = inspect_n7c1_plot_source_data(
        "01_clean_validation/clean_yaw_error_no_go2_vs_go2_horizontal.png",
        {
            "figure_path": str(fig),
            "figure_category": "clean",
            "series": [
                {"label": "no_go2", "x": [i * 0.25 for i in range(1200)], "y": [0.1] * 1200},
                {"label": "go2_horizontal", "x": [i * 0.25 for i in range(1200)], "y": [0.1] * 1200},
            ],
            "min_rows": 1000,
            "min_series": 2,
            "min_x_range": 200.0,
        },
    )
    assert not valid.empty_plot_suspect
    assert summarize_n7c1_plot_coverage([valid])["visual_validation_passed"] is True


def test_n7c1_update_residual_can_use_documented_aggregation(tmp_path):
    fig = tmp_path / "panel.png"
    fig.write_bytes(b"nonempty")
    aggregated = inspect_n7c1_plot_source_data(
        "03_update_residuals/go2_horizontal_prior_reject_panel.png",
        {
            "figure_path": str(fig),
            "figure_category": "update_residual",
            "series": [{"label": "updates", "x": [0], "y": [274]}],
            "update_count": 274,
            "documented_aggregation": True,
        },
    )
    assert "update_residual_rows_below_update_count" not in aggregated.reason_codes
