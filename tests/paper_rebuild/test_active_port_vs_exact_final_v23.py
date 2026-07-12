from scripts.paper_rebuild import finalize_clean1r2_blocked as finalizer


def test_active_port_parity_is_not_fabricated() -> None:
    record = finalizer.build_not_run_record("active_port_final_v23_parity")
    assert record["status"] == finalizer.UPSTREAM_NOT_RUN
    assert record["process_started"] is False
    assert record["output_generated"] is False
    assert record["metrics_generated"] is False


def test_all_four_methods_are_not_run_after_upstream_blocker() -> None:
    rows = finalizer.build_four_method_rows()
    assert [row["method_id"] for row in rows] == list(finalizer.METHOD_ORDER)
    assert all(row["status"] == finalizer.UPSTREAM_NOT_RUN for row in rows)
    assert all(row["solver_process_count"] == 0 for row in rows)
    assert all(row["formal_run_count"] == 0 for row in rows)
    assert all(row["metrics"] == "NOT_AVAILABLE_NO_RUN" for row in rows)
