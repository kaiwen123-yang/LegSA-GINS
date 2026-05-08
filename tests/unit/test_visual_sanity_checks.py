"""中文说明：测试图像 sanity check，不把视觉检查写成 formal pass。"""

from legsa_gins.visualization.visual_sanity_checks import (
    build_visual_sanity_report,
    check_no_nan_inf,
    check_required_figures,
    check_yaw_wrap_discontinuity,
    strict_yaw_gate_status,
)


def test_detects_yaw_wrap_spike():
    report = check_yaw_wrap_discontinuity(
        [
            {"timestamp": 0.0, "yaw_error_deg": 1.0},
            {"timestamp": 1.0, "yaw_error_deg": 120.0},
        ]
    )
    assert report["yaw_wrap_spike_detected"]


def test_missing_figures_and_no_nan_inf(tmp_path):
    required = check_required_figures(tmp_path)
    assert required["missing_figures"]
    assert check_no_nan_inf({"a": [1.0, 2.0]})["no_nan_inf"]
    assert not check_no_nan_inf({"a": [float("nan")]})["no_nan_inf"]


def test_yaw_near_boundary_not_relaxed():
    status = strict_yaw_gate_status(2.06058)
    assert not status["yaw_gate_pass"]
    assert status["yaw_near_boundary"]
    assert status["near_boundary_not_relaxed"]


def test_build_visual_sanity_report_flags_boundary(tmp_path):
    (tmp_path / "01_trajectory").mkdir()
    report = build_visual_sanity_report(
        output_dir=tmp_path,
        reference_rows=[{"timestamp": 0.0}, {"timestamp": 1.0}],
        estimate_rows=[{"timestamp": 0.0}, {"timestamp": 1.0}],
        error_series=[
            {"timestamp": 0.0, "horizontal_error_m": 0.2, "up_error_m": 0.0, "yaw_error_deg": 1.0},
            {"timestamp": 1.0, "horizontal_error_m": 0.3, "up_error_m": 0.0, "yaw_error_deg": 1.1},
        ],
        metrics_snapshot={"yaw_rmse_deg": 1.1},
        expected_count=2,
        expected_min_figures=1,
    )
    assert report["time_monotonic"]
    assert report["no_nan_inf"]
    assert report["manual_visual_review_required"]
    assert not report["numerical_performance_claim"]
