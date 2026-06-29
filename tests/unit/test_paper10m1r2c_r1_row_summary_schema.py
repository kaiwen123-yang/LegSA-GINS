import csv
import os
from pathlib import Path


REQUIRED_FIELDS = {
    "row_id",
    "case_id",
    "method_mode_id",
    "terminal_status",
    "solver_completed",
    "evaluator_completed",
    "nav_exists",
    "std_exists",
    "metrics_exists",
    "run_manifest_exists",
    "yaw_provider_lineage_reference_exists",
    "trace_used_online",
    "final_v23_output_used_as_input",
    "legsa_output_used_as_input",
    "benchmark_output_used_as_input",
    "horizontal_rmse_m",
    "yaw_rmse_deg",
    "trace_yaw_rmse_deg",
    "provider_reference_yaw_rmse_deg",
    "a1_yaw_update_count",
    "a1_yaw_accepted_count",
    "a1_yaw_downweighted_count",
    "a1_yaw_rejected_count",
}


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2C_R1_STAGE_ROOT must be set"
    return Path(root)


def test_row_summary_schema_and_completion_status():
    path = stage_root() / "05_EXECUTION" / "PAPER10M1R2C_R1_ROW_LEVEL_RESULT_TABLE.csv"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        assert REQUIRED_FIELDS.issubset(set(reader.fieldnames or []))
        rows = list(reader)
    assert len(rows) == 2164
    assert all(row["terminal_status"] == "COMPLETED_EVALUABLE" for row in rows)
    assert all(row["solver_completed"] == "true" for row in rows)
    assert all(row["evaluator_completed"] == "true" for row in rows)
