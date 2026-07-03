import csv
import os
from pathlib import Path

import pytest


def test_da2r2_no_old_aggregate_status():
    root = os.environ.get("PAPER10_DA2R2_STAGE_ROOT")
    if not root:
        pytest.skip("PAPER10_DA2R2_STAGE_ROOT not set")
    rows = list(csv.DictReader((Path(root) / "07_EVALUATION" / "DA2R2_ROW_LEVEL_RESULT_TABLE.csv").open()))
    assert "OLD_IMPORTED_AGGREGATE" not in {row["terminal_status"] for row in rows}
    assert all("old_aggregate" not in row["notes"] for row in rows)
