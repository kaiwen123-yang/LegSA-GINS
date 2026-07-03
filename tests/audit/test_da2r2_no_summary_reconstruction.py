import csv
import os
from pathlib import Path

import pytest


def test_da2r2_no_summary_reconstruction_status():
    root = os.environ.get("PAPER10_DA2R2_STAGE_ROOT")
    if not root:
        pytest.skip("PAPER10_DA2R2_STAGE_ROOT not set")
    rows = list(csv.DictReader((Path(root) / "07_EVALUATION" / "DA2R2_ROW_LEVEL_RESULT_TABLE.csv").open()))
    assert "SUMMARY_RECONSTRUCTED" not in {row["terminal_status"] for row in rows}
