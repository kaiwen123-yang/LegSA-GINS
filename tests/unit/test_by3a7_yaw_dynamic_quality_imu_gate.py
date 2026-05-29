import math

from scripts.experiments import run_by3a7_a1_yaw_dynamic_quality_imu_gate_repair as by3a7


def test_a1_quality_does_not_reject_on_trace_disagreement_only():
    quality = by3a7.classify_a1_epoch_quality(
        yaw_jump_deg=2.0,
        baseline_length_m=0.38,
        baseline_lower_m=0.2,
        baseline_upper_m=0.6,
        trace_diff_deg=90.0,
        hdt_diff_deg=None,
    )

    assert quality["should_use_for_solver_candidate"] is True
    assert quality["diagnostic_only"] is True
    assert quality["invalid_criteria_basis"] == "none"


def test_a1_quality_rejects_only_source_quality_or_large_jump():
    baseline = by3a7.classify_a1_epoch_quality(
        yaw_jump_deg=2.0,
        baseline_length_m=0.05,
        baseline_lower_m=0.2,
        baseline_upper_m=0.6,
        trace_diff_deg=0.0,
        hdt_diff_deg=0.0,
    )
    jump = by3a7.classify_a1_epoch_quality(
        yaw_jump_deg=50.0,
        baseline_length_m=0.38,
        baseline_lower_m=0.2,
        baseline_upper_m=0.6,
        trace_diff_deg=0.0,
        hdt_diff_deg=0.0,
    )

    assert baseline["should_use_for_solver_candidate"] is False
    assert "baseline_length_outside_robust_source_bounds" in baseline["invalid_criteria_basis"]
    assert jump["should_use_for_solver_candidate"] is False
    assert "yaw_jump_gt_45_deg_between_gnss_epochs" in jump["invalid_criteria_basis"]


def test_static_pre_motion_bias_uses_source_segment_before_go2_start():
    body_rows = []
    for i in range(5):
        body_rows.append(
            {
                "timestamp": str(float(i) * 0.01),
                "gyro_x": "0.0",
                "gyro_y": "0.0",
                "gyro_z": "0.0",
                "acc_x": "0.0",
                "acc_y": "0.0",
                "acc_z": "9.8",
            }
        )
    for i in range(5, 8):
        body_rows.append(
            {
                "timestamp": str(float(i) * 0.01),
                "gyro_x": "0.0",
                "gyro_y": "0.0",
                "gyro_z": "0.1",
                "acc_x": "0.0",
                "acc_y": "0.0",
                "acc_z": "9.8",
            }
        )

    bias = by3a7.compute_static_pre_motion_bias(body_rows, go2_start=0.05)
    repaired = by3a7.build_static_bias_imu_rows(
        body_rows,
        body_min=0.0,
        go2_start=0.05,
        static_bias=bias,
    )

    assert all(abs(value) < 1.0e-12 for value in bias)
    assert repaired
    assert math.degrees(sum(row[3] for row in repaired)) < 0.0
