from scripts.experiments import run_by3a8_yaw_error_budget_safe_repair as by3a8


def test_a1_quality_trace_disagreement_is_diagnostic_only():
    quality = by3a8.classify_a1_epoch_for_by3a8(
        yaw_jump_deg=2.0,
        next_yaw_jump_deg=1.0,
        baseline_length_m=0.38,
        baseline_lower_m=0.2,
        baseline_upper_m=0.6,
        trace_diff_deg=90.0,
        hdt_diff_deg=None,
    )

    assert quality["objective_invalid_for_solver_candidate"] is False
    assert quality["trace_disagreement_diagnostic_only"] is True
    assert quality["reason"] == "none"


def test_a1_quality_rejects_source_outlier_not_rmse():
    baseline = by3a8.classify_a1_epoch_for_by3a8(
        yaw_jump_deg=2.0,
        next_yaw_jump_deg=1.0,
        baseline_length_m=0.05,
        baseline_lower_m=0.2,
        baseline_upper_m=0.6,
        trace_diff_deg=0.0,
        hdt_diff_deg=0.0,
    )
    isolated = by3a8.classify_a1_epoch_for_by3a8(
        yaw_jump_deg=55.0,
        next_yaw_jump_deg=-52.0,
        baseline_length_m=0.38,
        baseline_lower_m=0.2,
        baseline_upper_m=0.6,
        trace_diff_deg=0.0,
        hdt_diff_deg=0.0,
    )

    assert baseline["objective_invalid_for_solver_candidate"] is True
    assert "baseline_length_outside_source_robust_bounds" in baseline["reason"]
    assert isolated["objective_invalid_for_solver_candidate"] is True
    assert "isolated_large_counter_jump" in isolated["reason"]


def test_time_lag_scan_is_never_repair_allowed_without_metadata():
    left_t = [float(i) for i in range(20)]
    left_angle = [float(i) for i in range(20)]
    right_t = [float(i) for i in range(20)]
    right_angle = [float(i + 1) for i in range(20)]

    result = by3a8.scan_lag_pair("synthetic", left_t, left_angle, right_t, right_angle)

    assert result["allowed_for_repair"] is False
    assert result["timestamp_metadata_supports_this_lag"] is False
    assert result["reason"] == "diagnostic only; no metadata-backed timestamp bug"


def test_circular_summary_wraps_mean_error():
    summary = by3a8.circular_summary([179.0, -179.0])

    assert abs(abs(summary["mean_circular_error_deg"]) - 180.0) < 1.0e-9
    assert summary["count"] == 2
