from pathlib import Path

from legsa_gins.raw_gnss.raw_doppler_plot_data_coverage import (
    inspect_plot_source_data,
    validate_required_figure_coverage,
)


def test_plot_data_coverage_detects_empty_figure_source(tmp_path: Path):
    # 中文说明：mandatory 图即使文件存在，只要没有绘图源数据也不能通过。
    fig = tmp_path / "empty.png"
    fig.write_text("placeholder", encoding="utf-8")
    coverage = inspect_plot_source_data(
        "01_clean_ablation_repaired/clean_horizontal_error_baseline_vs_raw_repaired.png",
        {"figure_path": str(fig), "mandatory": True, "series": [], "min_rows": 1000, "min_series": 2},
    )
    assert coverage.empty_plot_suspect is True
    assert "no_plotted_source_rows" in coverage.reason_codes
    summary = validate_required_figure_coverage([coverage])
    assert summary["mandatory_coverage_passed"] is False
    assert summary["required_figures_generated"] is False


def test_plot_data_coverage_detects_unreasonable_x_range(tmp_path: Path):
    fig = tmp_path / "short_axis.png"
    fig.write_text("placeholder", encoding="utf-8")
    coverage = inspect_plot_source_data(
        "01_clean_ablation_repaired/baseline_minus_raw_yaw_diff_repaired.png",
        {
            "figure_path": str(fig),
            "mandatory": True,
            "min_rows": 1000,
            "min_series": 1,
            "min_x_range": 200.0,
            "series": [{"label": "diff", "x": [0.0] * 1200, "y": [0.1] * 1200}],
        },
    )
    assert coverage.has_reasonable_time_axis is False
    assert "unreasonable_time_axis_range" in coverage.reason_codes


def test_plot_data_coverage_passes_nonempty_plot_data(tmp_path: Path):
    fig = tmp_path / "good.png"
    fig.write_text("placeholder", encoding="utf-8")
    rows = list(range(1200))
    coverage = inspect_plot_source_data(
        "01_clean_ablation_repaired/clean_yaw_error_baseline_vs_raw_repaired.png",
        {
            "figure_path": str(fig),
            "mandatory": True,
            "min_rows": 1000,
            "min_series": 2,
            "min_x_range": 200.0,
            "series": [
                {"label": "baseline", "x": [i * 0.25 for i in rows], "y": [0.2] * len(rows)},
                {"label": "raw", "x": [i * 0.25 for i in rows], "y": [0.1] * len(rows)},
            ],
        },
    )
    assert coverage.empty_plot_suspect is False
    assert coverage.total_plotted_row_count == 2400
    assert coverage.x_range and coverage.x_range > 200.0
