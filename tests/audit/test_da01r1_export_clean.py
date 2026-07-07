import json
import os
import zipfile
from pathlib import Path

import pytest


def test_da01r1_export_clean_has_no_forbidden_payloads():
    root_value = os.environ.get("DA01R1_EXPORT_CLEAN_ROOT")
    if not root_value:
        pytest.skip("DA01R1_EXPORT_CLEAN_ROOT not set")
    root = Path(root_value)
    scan = json.loads((root / "export_clean_path_scan.json").read_text(encoding="utf-8"))
    assert scan["violations"] == []
    package = root / "paper10_da3_da01r1_los_dd_repair_pack.zip"
    assert package.exists()
    forbidden = ("gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv", "by2.txt", "trace_vrtk2", "epoch_output.csv", ".ubx", ".obs", ".nav")
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
    assert names
    assert not any(any(token in name for token in forbidden) for name in names)
