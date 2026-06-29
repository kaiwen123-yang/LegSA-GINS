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


def test_method_summary_has_four_modes_and_541_completed_each():
    rows = read_csv(stage_root() / "07_METHOD_SUMMARIES" / "PAPER10M1R2C_R1_METHOD_LEVEL_SUMMARY.csv")
    assert len(rows) == 4
    for row in rows:
        assert int(row["planned_rows"]) == 541
        assert int(row["completed_rows"]) == 541
        assert int(row["failed_rows"]) == 0
        assert int(row["blocked_rows"]) == 0
        assert int(row["skipped_rows"]) == 0


def test_method_comparison_table_is_bounded():
    rows = read_csv(stage_root() / "07_METHOD_SUMMARIES" / "PAPER10M1R2C_R1_METHOD_MODE_COMPARISON_TABLE.csv")
    assert rows
    assert all(row["claim_level"] == "bounded_engineering_result" for row in rows)
    assert all("No universal superiority" in row["caveat"] for row in rows)
