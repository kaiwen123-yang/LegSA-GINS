from scripts.paper_rebuild import finalize_clean1r2_blocked as finalizer


def test_exact_evaluator_identity_and_interpolation_contract() -> None:
    evaluator = finalizer.load_contract()["evaluator_contract"]
    assert evaluator["evaluator_sha256"] == finalizer.CORE_HASHES["evaluator"]
    assert evaluator["solver_nav_columns_zero_based"] == {
        "time": 1,
        "latitude": 2,
        "longitude": 3,
        "height": 4,
        "roll": 8,
        "pitch": 9,
        "yaw": 10,
    }
    assert evaluator["match_tolerance_seconds"] == "none"
    assert evaluator["denominator"] == "retained_NAV_epoch_count"
    assert evaluator["reference_yaw_conversion"] == "wrap360(90_deg_minus_trace_ENU_yaw)"


def test_blocked_reporting_never_opens_trace_or_generates_metrics() -> None:
    record = finalizer.build_not_run_record("exact_archived_final_v23_fresh_run")
    assert record["trace_read"] is False
    assert record["metrics_generated"] is False
    assert record["legacy_solver_input"] is False
