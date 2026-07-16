from __future__ import annotations

from pathlib import Path

from scripts.paper_rebuild import finalize_clean1r2_blocked as finalizer


def _row(time_s: float) -> str:
    values = [
        time_s,
        39.0,
        116.0,
        40.0,
        0.1,
        0.1,
        0.2,
        1.0,
        2.0,
        3.0,
        0.05,
        0.05,
        0.05,
        10.0,
        1.5,
    ]
    return " ".join(str(value) for value in values)


def test_archived_input_inspection_never_promotes_solver_eligibility(
    tmp_path: Path,
) -> None:
    archived = tmp_path / "input.gnss"
    archived.write_text(_row(55.0) + "\n" + _row(66.0) + "\n", encoding="utf-8")
    metadata = finalizer.inspect_archived_input(archived)
    assert metadata["row_count"] == 2
    assert metadata["column_count_values"] == [15]
    assert metadata["rows_inside_runtime_window"] == 1
    assert metadata["evidence_classification"] == "PARITY_REFERENCE_ONLY"
    assert metadata["solver_input_eligible"] is False


def test_fresh_input_is_truthfully_not_run() -> None:
    record = finalizer.build_not_run_record("fresh_final_v23_input_generation")
    assert record["status"] == finalizer.UPSTREAM_NOT_RUN
    assert record["process_started"] is False
    assert record["output_generated"] is False
    assert record["trace_read"] is False
