import json
import os
from pathlib import Path

import pytest


def test_da01r2b_export_clean_scan_has_no_violations():
    export_root = os.environ.get("DA01R2B_EXPORT_CLEAN_ROOT")
    if not export_root:
        pytest.skip("DA01R2B_EXPORT_CLEAN_ROOT is not set")
    root = Path(export_root)
    scan_path = root / "export_clean_path_scan.json"
    zip_path = root / "paper10_da3_da01r2b_validity_raw_unsupported_pack.zip"
    assert scan_path.exists()
    assert zip_path.exists()
    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    assert scan["violations"] == []
    manifest = (root / "export_clean_manifest.csv").read_text(encoding="utf-8")
    for token in ("gnss1-raw.csv", "gnss2-raw.csv", "by2.txt", "trace_vrtk2", "epoch_output.csv"):
        assert token not in manifest
