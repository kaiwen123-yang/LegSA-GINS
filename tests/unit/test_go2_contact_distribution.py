"""中文说明：N7B2 contact distribution 只统计 Go2 field，不使用 truth。"""

from legsa_gins.go2_prior.go2_contact_distribution import analyze_contact_distribution


def _row(force: float, speed: float, *, mode: str = "walk", gait_type: int = 1) -> dict[str, float | str | int]:
    return {
        "aligned_time": 0.0,
        "mode": mode,
        "gait_type": gait_type,
        "body_height": 0.32,
        "go2_velocity_0": 0.4 if mode == "walk" else 0.02,
        "go2_velocity_1": 0.0,
        "go2_velocity_2": 0.0,
        **{f"foot_force_{foot}": force + foot for foot in range(4)},
        **{f"foot_speed_body_{axis}": speed for axis in range(12)},
    }


def test_contact_distribution_reports_field_quality_and_boundaries():
    report = analyze_contact_distribution([_row(5.0, 0.2), _row(30.0, 0.03, mode="stand", gait_type=0)])
    assert report["row_count"] == 2
    assert report["field_quality_status"] == "usable"
    assert report["distribution_source"] == "go2_field_distribution_only"
    assert report["trace_solver_input"] is False
    assert report["final_v23_output_solver_input"] is False
    assert report["foot_force_stats_by_foot"]["foot_0"]["p50"] is not None
    assert report["foot_speed_norm_stats_by_foot"]["foot_0"]["p95"] is not None
