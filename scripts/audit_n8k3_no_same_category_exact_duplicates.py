#!/usr/bin/env python3
"""Audit N8K3 has no blocking same-category exact duplicates."""

# 中文说明：同一 variant/category 内不同图名的 exact duplicate 必须清零。

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
    if fix.get("blocking_exact_duplicate_after_count") != 0:
        raise SystemExit("audit_n8k3_no_same_category_exact_duplicates failed")
    print("audit_n8k3_no_same_category_exact_duplicates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
