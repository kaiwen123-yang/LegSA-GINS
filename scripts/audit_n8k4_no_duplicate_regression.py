#!/usr/bin/env python3
"""Audit N8K4 did not reintroduce duplicate plots."""

# 中文说明：N8K4 修复语义错位时不能重新制造同类 exact duplicate。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k4_semantic_filename_alignment import make_toy_n8k4_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k4"
            make_toy_n8k4_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    duplicate = json.loads((root / "N8K4_DUPLICATE_REGRESSION_REPORT.json").read_text(encoding="utf-8"))
    if duplicate.get("same_category_exact_duplicate_remaining") != 0 or duplicate.get("perceptual_duplicate_after_count") != 0:
        raise SystemExit("audit_n8k4_no_duplicate_regression failed")
    print("audit_n8k4_no_duplicate_regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
