import csv
import os
from pathlib import Path

import pytest


def test_da2r2_no_trace_online():
    root = os.environ.get("PAPER10_DA2R2_STAGE_ROOT")
    if not root:
        pytest.skip("PAPER10_DA2R2_STAGE_ROOT not set")
    rows = list(csv.DictReader((Path(root) / "07_EVALUATION" / "DA2R2_ROW_LEVEL_RESULT_TABLE.csv").open()))
    assert {row["trace_used_online"] for row in rows} == {"false"}
