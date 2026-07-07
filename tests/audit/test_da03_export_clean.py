import json
import os
from pathlib import Path

import pytest


def test_da03_export_clean_scan_has_no_violations():
    export_root = os.environ.get("DA03_EXPORT_CLEAN_ROOT")
    if not export_root:
        pytest.skip("DA03_EXPORT_CLEAN_ROOT is not set")
    root = Path(export_root)
    scan = json.loads((root / "export_clean_path_scan.json").read_text(encoding="utf-8"))
    assert scan["violations"] == []
    assert (root / "paper10_da3_da03_liu_cwls_pack.zip").exists()
    manifest = (root / "export_clean_manifest.csv").read_text(encoding="utf-8")
    for token in ("gnss1-raw.csv", "gnss2-raw.csv", "by2.txt", "trace_vrtk2", "epoch_output.csv"):
        assert token not in manifest
