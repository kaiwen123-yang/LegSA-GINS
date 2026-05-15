#!/usr/bin/env python3
"""Audit N8K5 introduces no duplicate regression."""

# 中文说明：N8K5 不能重新引入 same-category 或阻塞 cross-category duplicate。

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
    duplicate = json.loads((root / "N8K5_DUPLICATE_REGRESSION_REPORT.json").read_text(encoding="utf-8"))
    if duplicate.get("same_category_exact_duplicate_after") != 0:
        raise SystemExit("audit_n8k5_no_duplicate_regression failed: same-category duplicate")
    if duplicate.get("same_variant_cross_category_duplicate_after") != 0:
        raise SystemExit("audit_n8k5_no_duplicate_regression failed: cross-category duplicate")
    if duplicate.get("blocking_cross_category_duplicate_patterns_after"):
        raise SystemExit("audit_n8k5_no_duplicate_regression failed: blocking pattern")
    print("audit_n8k5_no_duplicate_regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
