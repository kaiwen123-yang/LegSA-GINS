import csv
import os
from pathlib import Path


def stage_root() -> Path:
    root = os.environ.get("PAPER10M1R2D_R1_STAGE_ROOT")
    assert root, "PAPER10M1R2D_R1_STAGE_ROOT must be set"
    return Path(root)


def test_row_ids_are_d_r1_and_not_old_m1r2c_imports():
    path = stage_root() / "05_EXECUTION" / "PAPER10M1R2D_R1_ROW_LEVEL_RESULT_TABLE.csv"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["row_id"].startswith("PAPER10M1R2D_R1_") for row in rows)
    assert all("PAPER10M1R2C_R1_" not in row["row_id"] for row in rows)
    assert all("old" not in row.get("notes", "").lower() for row in rows)
