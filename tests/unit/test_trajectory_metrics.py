"""中文说明：N4F trajectory metrics 只验证 evaluator，不读取真实 BY2。"""

from legsa_gins.evaluation.trajectory_metrics import (
    align_by_timestamp,
    compute_errors,
    summary_metrics,
)


def test_trajectory_metrics_align_and_summarize():
    est = [
        {
            "timestamp": 1.00,
            "lat_deg": 30.000001,
            "lon_deg": 120.0,
            "height_m": 11.0,
            "roll_deg": 1.0,
            "pitch_deg": -2.0,
            "yaw_deg": 179.0,
        },
        {
            "timestamp": 1.10,
            "lat_deg": 30.000002,
            "lon_deg": 120.0,
            "height_m": 12.0,
            "roll_deg": 2.0,
            "pitch_deg": -1.0,
            "yaw_deg": -179.0,
        },
    ]
    ref = [
        {
            "timestamp": 1.01,
            "lat_deg": 30.0,
            "lon_deg": 120.0,
            "height_m": 10.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": -179.0,
        },
        {
            "timestamp": 1.11,
            "lat_deg": 30.0,
            "lon_deg": 120.0,
            "height_m": 10.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": 179.0,
        },
    ]

    aligned = align_by_timestamp(est, ref, max_dt=0.05)
    errors = compute_errors(aligned)
    summary = summary_metrics(errors)

    assert len(aligned) == 2
    assert errors[0]["yaw_error_deg"] == -2.0
    assert errors[1]["yaw_error_deg"] == 2.0
    assert summary["count"] == 2
    assert summary["trace_solver_input"] is False
    assert summary["bad_epoch_deletion_for_metric"] is False
    assert summary["horizontal_rmse_m"] > 0.0

