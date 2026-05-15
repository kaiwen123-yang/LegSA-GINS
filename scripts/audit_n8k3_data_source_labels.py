#!/usr/bin/env python3
"""Audit N8K3 derived data source labels."""

# 中文说明：derived_from_n8k_metrics_and_baseline_nav 必须显式标注为 surrogate/derived。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k3_duplicate_semantic_plots import make_toy_n8k3_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k3"
            make_toy_n8k3_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    fix = json.loads((root / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json").read_text(encoding="utf-8"))
    if fix.get("derived_data_labels_count", 0) <= 0:
        raise SystemExit("audit_n8k3_data_source_labels failed")
    for entry in fix.get("fixed_entries", []):
        if entry.get("data_source") == "derived_from_n8k_metrics_and_baseline_nav" and entry.get("visualization_type") != "derived/surrogate":
            raise SystemExit("audit_n8k3_data_source_labels failed")
    print("audit_n8k3_data_source_labels passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
