#!/usr/bin/env python3
"""Audit N8K6 did not reintroduce duplicate plot blockers."""

# 中文说明：A0 修复不能重新引入同类或跨类重复图。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k6_a0_feedback_applicability import make_toy_n8k6_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k6"
            make_toy_n8k6_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    duplicate = json.loads((root / "N8K6_DUPLICATE_REGRESSION_REPORT.json").read_text(encoding="utf-8"))
    if duplicate.get("exact_same_category_duplicate_after") != 0:
        raise SystemExit("audit_n8k6_no_duplicate_regression failed: same-category")
    if duplicate.get("same_variant_cross_category_duplicate_after") != 0:
        raise SystemExit("audit_n8k6_no_duplicate_regression failed: cross-category")
    if duplicate.get("blocking_duplicate_pairs_after"):
        raise SystemExit("audit_n8k6_no_duplicate_regression failed: blocking pairs")
    print("audit_n8k6_no_duplicate_regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
