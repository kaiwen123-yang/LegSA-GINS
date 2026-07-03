import json
import os
from pathlib import Path

import pytest


def test_da2r2_export_clean_scan_passes():
    root = os.environ.get("PAPER10_DA2R2_EXPORT_ROOT")
    if not root:
        pytest.skip("PAPER10_DA2R2_EXPORT_ROOT not set")
    scan = json.loads((Path(root) / "11_EXPORT_CLEAN_FOR_GPT" / "export_clean_path_scan.json").read_text())
    assert scan["status"] == "PASS"
    assert scan["zip_content_status"] == "PASS"
    assert scan["hit_count"] == 0
    assert scan["zip_hit_count"] == 0
