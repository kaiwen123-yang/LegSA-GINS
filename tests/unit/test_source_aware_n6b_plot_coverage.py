from pathlib import Path

from legsa_gins.source_aware.source_aware_n6b_plot_coverage import (
    inspect_n6b1_plot_source_data,
    summarize_n6b1_plot_coverage,
)


def test_n6b1_plot_coverage_zero_rows_fails(tmp_path: Path):
    # 中文说明：mandatory clean 图没有 plotted rows 时必须失败。
    figure = tmp_path / "figure.png"
    figure.write_bytes(b"x")
    coverage = inspect_n6b1_plot_source_data(
        "01_clean_validation/clean_horizontal_error_no_sourceaware_vs_n6b.png",
        {"figure_path": str(figure), "figure_category": "clean", "series": [], "min_rows": 1000, "min_series": 2, "min_x_range": 200.0},
    )
    assert coverage.empty_plot_suspect is True
    assert "no_plotted_source_rows" in coverage.reason_codes


def test_n6b1_plot_coverage_valid_clean_passes(tmp_path: Path):
    # 中文说明：有效 clean 图必须同时满足行数、series 和时间轴覆盖。
    figure = tmp_path / "figure.png"
    figure.write_bytes(b"x")
    x = [index * 0.25 for index in range(1200)]
    coverage = inspect_n6b1_plot_source_data(
        "01_clean_validation/clean_yaw_error_no_sourceaware_vs_n6b.png",
        {
            "figure_path": str(figure),
            "figure_category": "clean",
            "series": [{"label": "no_sourceaware", "x": x, "y": [0.1] * 1200}, {"label": "n6b", "x": x, "y": [0.2] * 1200}],
            "min_rows": 1000,
            "min_series": 2,
            "min_x_range": 200.0,
        },
    )
    report = summarize_n6b1_plot_coverage([coverage])
    assert coverage.empty_plot_suspect is False
    assert report["visual_validation_passed"] is True


def test_n6b1_weight_trace_requires_four_sources(tmp_path: Path):
    # 中文说明：source-aware 权重图必须覆盖四类 source，不能只画局部源。
    figure = tmp_path / "figure.png"
    figure.write_bytes(b"x")
    coverage = inspect_n6b1_plot_source_data(
        "02_weight_traces/n6b_R_scale_by_source_time.png",
        {
            "figure_path": str(figure),
            "figure_category": "weight_trace",
            "source_ids": ["receiver_position"],
            "series": [{"label": "receiver_position", "x": [0, 1], "y": [1, 1.1]}],
            "min_rows": 1,
            "min_series": 1,
        },
    )
    assert "weight_trace_source_ids_below_requirement" in coverage.reason_codes
