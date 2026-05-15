#!/usr/bin/env python3
"""Audit N8K5 preserves derived/surrogate data source labels."""

# 中文说明：derived_from_n8k_metrics_and_baseline_nav 不能被写成完整 runtime variant NAV。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k5_cross_category_duplicate_plots import make_toy_n8k5_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k5"
            make_toy_n8k5_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    fix = json.loads((root / "N8K5_CROSS_CATEGORY_SEMANTIC_FIX_REPORT.json").read_text(encoding="utf-8"))
    if fix.get("derived_data_labels_count", 0) <= 0 or fix.get("derived_surrogate_labels_count", 0) <= 0:
        raise SystemExit("audit_n8k5_data_source_labels failed")
    print("audit_n8k5_data_source_labels passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
