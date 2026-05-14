"""中文说明：测试 N8C plot coverage 规则。"""

from legsa_gins.fgo.fgo_n8c_plot_coverage import build_plot_coverage_report, coverage_entry


def test_n8c_plot_coverage_detects_nonempty_time_series() -> None:
    entry = coverage_entry(
        figure_name="ekf_vs_fgo_weak_yaw_yaw_error.png",
        series=[[0.0, 1.0, 2.0, 3.0]],
        x_values=[0.0, 100.0, 200.0, 300.0],
        figure_path=None,
    )
    assert entry["x_range"] == 300.0
    assert entry["time_monotonic"]
    report = build_plot_coverage_report([entry])
    assert not report["all_mandatory_figures_present"]
