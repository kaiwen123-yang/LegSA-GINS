from scripts.paper_rebuild import finalize_clean1r2_blocked as finalizer


def test_active_port_parity_is_not_fabricated() -> None:
    record = finalizer.build_not_run_record("active_port_final_v23_parity")
    assert record["status"] == finalizer.UPSTREAM_NOT_RUN
    assert record["process_started"] is False
    assert record["output_generated"] is False
    assert record["metrics_generated"] is False


def test_active_solver_and_provider_parser_change_are_not_conflated() -> None:
    source = (
        finalizer.REPO_ROOT
        / "scripts/paper_rebuild/finalize_clean1r2_blocked.py"
    ).read_text(encoding="utf-8")
    assert '"active_parity_solver_modified": False' in source
    assert '"active_clean_provider_parser_modified": True' in source
    assert '"active_port_modified"' not in source


def test_all_four_methods_are_not_run_after_upstream_blocker() -> None:
    rows = finalizer.build_four_method_rows()
    assert [row["method_id"] for row in rows] == list(finalizer.METHOD_ORDER)
    assert all(row["status"] == finalizer.UPSTREAM_NOT_RUN for row in rows)
    assert all(row["solver_process_count"] == 0 for row in rows)
    assert all(row["formal_run_count"] == 0 for row in rows)
    assert all(row["metrics"] == "NOT_AVAILABLE_NO_RUN" for row in rows)
