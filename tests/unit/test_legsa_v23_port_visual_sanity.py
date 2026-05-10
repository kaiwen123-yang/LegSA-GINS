"""中文说明：测试 N4H4E visual sanity 的图像候选通过和异常拦截规则。"""

from legsa_gins.visualization.legsa_v23_port_visual_plots import REQUIRED_FIGURE_NAMES
from legsa_gins.visualization.legsa_v23_port_visual_sanity import (
    build_visual_sanity_report,
    required_figures_generated,
    yaw_wrap_spike_detected,
)


def _nav_rows():
    return [
        {
            "timestamp": 0.0,
            "lat_deg": 30.0,
            "lon_deg": 120.0,
            "height_m": 10.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": 1.0,
        },
        {
            "timestamp": 0.01,
            "lat_deg": 30.0,
            "lon_deg": 120.0,
            "height_m": 10.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": 1.1,
        },
    ]


def _errors():
    return [
        {
            "timestamp": 0.0,
            "horizontal_error_m": 0.2,
            "up_error_m": 0.1,
            "roll_error_deg": 0.1,
            "pitch_error_deg": 0.1,
            "yaw_error_deg": 0.2,
        },
        {
            "timestamp": 0.01,
            "horizontal_error_m": 0.3,
            "up_error_m": 0.2,
            "roll_error_deg": 0.1,
            "pitch_error_deg": 0.1,
            "yaw_error_deg": 0.3,
        },
    ]


def test_detects_yaw_wrap_spike():
    assert yaw_wrap_spike_detected([{"yaw_error_deg": 0.0}, {"yaw_error_deg": 181.0}]) is True


def test_detects_missing_required_figures(tmp_path):
    status = required_figures_generated(tmp_path)
    assert status["required_figures_generated"] is False
    assert "01_trajectory/trajectory_xy_port_finalv23_reference.png" in status["missing_required_figures"]


def test_visual_candidate_decision_passes_when_sane(tmp_path):
    for rel in REQUIRED_FIGURE_NAMES:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"toy")
    inputs = {
        "port_rows": _nav_rows(),
        "final_v23_rows": _nav_rows(),
        "trace_rows": _nav_rows(),
        "r3c_reports": {
            "PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json": {"port_absolute_close_to_finalv23_absolute": True},
            "PORT_VS_FINALV23_NAV_PARITY_REPORT.json": {"parity_small": True},
            "FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json": {"official_summary_reproduced": True},
        },
    }
    plot_report = {
        "errors": {
            "port_vs_trace": _errors(),
            "final_v23_vs_trace": _errors(),
            "port_vs_final_v23": _errors(),
        },
        "figure_count_total": len(REQUIRED_FIGURE_NAMES),
        "pure_single_comparison_absent": True,
    }

    report = build_visual_sanity_report(
        inputs=inputs,
        plot_report=plot_report,
        figure_output_dir=tmp_path,
        aligned_count_minimum=2,
    )

    assert report["visual_candidate_passed"] is True
    assert report["manual_visual_review_required"] is True
    assert report["paper_performance_claim"] is False
