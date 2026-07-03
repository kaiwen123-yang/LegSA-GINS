import csv
import os
from pathlib import Path

import pytest


def test_da2r2_no_receiver_imu_as_body():
    root = os.environ.get("PAPER10_DA2R2_STAGE_ROOT")
    if not root:
        pytest.skip("PAPER10_DA2R2_STAGE_ROOT not set")
    rows = list(csv.DictReader((Path(root) / "07_EVALUATION" / "DA2R2_ROW_LEVEL_RESULT_TABLE.csv").open()))
    assert {row["receiver_imu_as_body_imu"] for row in rows} == {"false"}
