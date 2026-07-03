import csv
import os
from pathlib import Path

import pytest

from legsa_gins.external_literature.by2_classic_case_manifest import classic_case_manifest
from legsa_gins.external_literature.method_contracts import DA2R2_METHODS


def test_da2r2_planned_matrix_size_is_min3_classic():
    assert len(DA2R2_METHODS) == 3
    assert len(classic_case_manifest()) == 18
    assert len(DA2R2_METHODS) * len(classic_case_manifest()) == 54


def test_da2r2_stage_row_table_if_available():
    root = os.environ.get("PAPER10_DA2R2_STAGE_ROOT")
    if not root:
        pytest.skip("PAPER10_DA2R2_STAGE_ROOT not set")
    table = Path(root) / "07_EVALUATION" / "DA2R2_ROW_LEVEL_RESULT_TABLE.csv"
    rows = list(csv.DictReader(table.open()))
    assert len(rows) >= 54
    assert sum(row["completed_evaluable"] == "true" for row in rows) >= 54
