import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_STAGE_ROOT")
    assert root, "PAPER10M1R2C_STAGE_ROOT must be set for M1R2C artifact tests"
    return Path(root)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_qm_trace_summary_contains_full_candidate_rows():
    rows = read_csv(stage_root() / "07_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_QM_TRACE_SUMMARY.csv")
    full_rows = [row for row in rows if row["method_mode_id"] == "legsa_full_candidate_with_qm"]
    assert len(full_rows) == 541
    assert all(row["qm_state_count_summary"] for row in full_rows)


def test_module_action_summary_contains_raw_doppler_and_go2_columns():
    rows = read_csv(stage_root() / "07_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_MODULE_ACTION_SUMMARY.csv")
    assert rows
    assert {"raw_doppler_update_count", "go2_prior_update_count", "source_aware_update_count"}.issubset(rows[0])
