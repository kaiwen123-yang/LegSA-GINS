from scripts.paper_rebuild import finalize_clean1r2_blocked as finalizer


def test_same_run_window_and_initialization_are_recovered() -> None:
    contract = finalizer.load_contract()
    assert contract["time_contract"]["base_time_unix_seconds"] == 1772784000.0
    assert contract["time_contract"]["starttime_seconds"] == 66.0
    assert contract["time_contract"]["endtime_seconds"] == 340.0
    init = contract["runtime_initialization"]
    assert init["initpos_deg_deg_m"] == [39.98482973, 116.34312609, 41.80208107]
    assert init["initvel_ned_mps"] == [0.0, 0.0, 0.0]
    assert init["initatt_rpy_deg"] == [0.0, 0.0, 0.688505]
    assert contract["filter_contract"]["antlever_frd_m"] == [0.03, 0.03, -0.3]


def test_parity_and_four_method_gates_remain_closed() -> None:
    status = finalizer.load_contract()["execution_status"]
    assert status["fresh_final_v23_input"] == finalizer.UPSTREAM_NOT_RUN
    assert status["exact_final_v23_fresh_run"] == finalizer.UPSTREAM_NOT_RUN
    assert status["active_port_final_v23_parity"] == finalizer.UPSTREAM_NOT_RUN
    assert status["four_method_execution"] == finalizer.UPSTREAM_NOT_RUN
    assert status["current_solver_process_count"] == 0
    assert status["current_formal_run_count"] == 0
    assert status["trace_opened_for_current_evaluation"] is False


def test_v3_foot_aware_source_is_present_but_runtime_excluded() -> None:
    excluded = finalizer.load_contract()["excluded_extensions"]
    foot = excluded["v3_foot_aware"]
    assert foot["source_present_in_exact_tag"] is True
    assert foot["exact_tag_default_enabled"] is False
    assert foot["selected_same_run_foot_marker_count"] == 0
    assert foot["selected_same_run_enabled"] is False
    assert foot["selected_for_parity_contract"] is False
    for name in (
        "v2_4_quality_manager",
        "v4_raw_gnss_frontend",
        "qa_fallback",
        "fgo",
    ):
        assert excluded[name]["selected_for_parity_contract"] is False
