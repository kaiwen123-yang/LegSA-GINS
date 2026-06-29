import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2C_R1_STAGE_ROOT must be set"
    return Path(root)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_qm_trace_summary_contains_full_candidate_rows_with_split_fields():
    rows = read_csv(stage_root() / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_QM_TRACE_SUMMARY.csv")
    full_rows = [row for row in rows if row["method_mode_id"] == "legsa_full_candidate_with_qm"]
    assert len(full_rows) == 541
    assert all(row["qm_trace_required"] == "true" for row in full_rows)
    assert all(row["qm_trace_file_exists"] == "true" for row in full_rows)


def test_a1_action_audit_contains_split_counters():
    rows = read_csv(stage_root() / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_A1_YAW_ACTION_AUDIT.csv")
    assert rows
    assert {"a1_yaw_update_count", "a1_yaw_accepted_count", "a1_yaw_downweighted_count", "a1_yaw_rejected_count"}.issubset(
        rows[0]
    )
