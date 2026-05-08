"""中文说明：N4H0 measurement floor 单元测试不运行 proposed solver。"""

from legsa_gins.evaluation.measurement_floor import (
    compare_filter_trial_to_measurement_floor,
    evaluate_measurement_floor,
    make_direct_receiver_eval_nav,
)


def test_direct_receiver_eval_nav_heading_candidates_and_summary():
    receiver_rows = []
    trace_rows = []
    for index in range(5):
        receiver_rows.append(
            {
                "algo_time_sec": str(index * 0.05),
                "raw_time": str(1700000000.0 + index * 0.05),
                "lat_deg": "30.0",
                "lon_deg": f"{120.0 + index * 1.0e-7:.12f}",
                "height_m": "15.0",
                "has_position": "true",
                "heading_deg": "350.0",
                "heading_valid": "true",
            }
        )
        trace_rows.append(
            {
                "timestamp": index * 0.05,
                "lat_deg": 30.0,
                "lon_deg": 120.0 + index * 1.0e-7,
                "height_m": 15.0,
                "roll_deg": 0.0,
                "pitch_deg": 0.0,
                "yaw_deg": 80.0,
            }
        )

    no_offset = make_direct_receiver_eval_nav(
        receiver_rows,
        source_name="gnss1",
        heading_offset_mode="no_offset",
    )
    plus90 = make_direct_receiver_eval_nav(
        receiver_rows,
        source_name="gnss1",
        heading_offset_mode="plus90",
    )
    minus90 = make_direct_receiver_eval_nav(
        receiver_rows,
        source_name="gnss1",
        heading_offset_mode="minus90",
    )

    assert no_offset[0]["yaw_deg"] == 350.0
    assert plus90[0]["yaw_deg"] == 80.0
    assert minus90[0]["yaw_deg"] == 260.0
    assert plus90[0]["source_role"] == "measurement_floor"
    assert plus90[0]["trace_solver_input"] is False

    summary = evaluate_measurement_floor(plus90, trace_rows, max_dt=0.05)
    assert summary["count"] == 5
    assert summary["horizontal_rmse_m"] == 0.0
    assert summary["yaw_rmse_deg"] == 0.0
    assert summary["trace_solver_input"] is False
    assert summary["proposed_solver_output"] is False


def test_compare_filter_trial_to_measurement_floor_classification():
    comparison = compare_filter_trial_to_measurement_floor(
        {"horizontal_rmse_m": 14.86, "yaw_rmse_deg": 64.0},
        {
            "horizontal_rmse_m": 0.5,
            "up_rmse_m": 0.2,
            "yaw_rmse_deg": 1.0,
            "roll_rmse_deg": 0.0,
            "pitch_rmse_deg": 0.0,
        },
    )
    assert comparison["likely_filter_issue"] is True
    assert comparison["likely_input_or_evaluator_issue"] is False
    assert comparison["recommended_next_stage"] == "N4H_full_kf_gins_style_ekf_reconstruction"

    bad_floor = compare_filter_trial_to_measurement_floor(
        {"horizontal_rmse_m": 14.86},
        {"horizontal_rmse_m": 8.0, "up_rmse_m": 0.2, "yaw_rmse_deg": 3.0},
    )
    assert bad_floor["likely_input_or_evaluator_issue"] is True
    assert bad_floor["recommended_next_stage"] == "input_source_or_final_v23_input_parity_audit"
