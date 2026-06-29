import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2C_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2C_R1_STAGE_ROOT must be set"
    return Path(root)


def test_no_trace_online_in_row_table():
    with (stage_root() / "05_EXECUTION" / "PAPER10M1R2C_R1_ROW_LEVEL_RESULT_TABLE.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["trace_used_online"] == "false" for row in rows)
    assert all(row["trace_solver_input"] == "false" for row in rows)
