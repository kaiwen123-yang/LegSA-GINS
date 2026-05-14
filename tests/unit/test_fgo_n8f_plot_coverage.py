"""Unit tests for N8F1 plot coverage.

中文说明：检查强制图像覆盖率报告的 pass/fail 逻辑。
"""

from legsa_gins.fgo.fgo_n8f_plot_coverage import MANDATORY_N8F1_FIGURES, build_n8f1_plot_coverage_report, build_series_coverage


def test_plot_coverage_passes_with_all_figures() -> None:
    rows = [build_series_coverage(figure_name=name, series=[{"time": 0.0, "value": 1.0}]) for name in MANDATORY_N8F1_FIGURES]
    report = build_n8f1_plot_coverage_report(
        figure_manifest={"required_figures_nonempty": True},
        coverage_rows=rows,
        n8f_reports={
            "contact_weighting": {"rows": 1},
            "foot_kinematic": {"residual_rows": 1},
            "yawrate": {"residual_rows": 1},
            "relative_odometry": {"residual_rows": 1},
        },
    )
    assert report["visual_validation_passed"] is True

