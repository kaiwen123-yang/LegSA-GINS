#!/usr/bin/env python3
"""Audit N8K5 has no blocking cross-category duplicate pairs."""

# 中文说明：velocity compare 和 feedback delta 不能复制其它类别中的图。

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
    duplicate = json.loads((root / "N8K5_DUPLICATE_REGRESSION_REPORT.json").read_text(encoding="utf-8"))
    if fix.get("velocity_residual_vs_compare_velocity_duplicate_count_after") != 0:
        raise SystemExit("audit_n8k5_no_blocking_cross_category_duplicates failed: velocity pair")
    if fix.get("feedback_quality_vs_compare_feedback_delta_duplicate_count_after") != 0:
        raise SystemExit("audit_n8k5_no_blocking_cross_category_duplicates failed: feedback pair")
    if duplicate.get("blocking_cross_category_duplicate_patterns_after"):
        raise SystemExit("audit_n8k5_no_blocking_cross_category_duplicates failed: blocking patterns remain")
    print("audit_n8k5_no_blocking_cross_category_duplicates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
