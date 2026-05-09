"""中文说明：测试 R3B over-close 只报警，不写 outperform claim。"""

from legsa_gins.evaluation.legsa_v23_port_overclose_audit import analyze_overclose


def test_detects_too_good_relative_to_external():
    report = analyze_overclose(
        {
            "horizontal_rmse_m": 0.05,
            "up_rmse_m": 0.05,
            "yaw_rmse_deg": 0.3,
            "roll_rmse_deg": 0.04,
            "pitch_rmse_deg": 0.03,
        }
    )
    assert report["metric_gate_passed"] is True
    assert report["external_closeness_failed"] is True
    assert report["too_good_relative_to_external_clean"] is True
    assert report["paper_performance_claim"] is False


def test_distinguishes_metric_pass_from_external_closeness():
    report = analyze_overclose(
        {
            "horizontal_rmse_m": 0.35,
            "up_rmse_m": 0.80,
            "yaw_rmse_deg": 1.9,
            "roll_rmse_deg": 1.0,
            "pitch_rmse_deg": 1.5,
        }
    )
    assert report["metric_gate_passed"] is True
    assert report["external_closeness_failed"] is False
