#!/usr/bin/env python3
"""Audit N8K5 replaces empty feedback axes with not-applicable panels."""

# 中文说明：无 feedback rows 的 variant 不能画空 accept/reject 坐标轴。

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
    if fix.get("feedback_empty_axis_before_count", 0) <= 0:
        raise SystemExit("audit_n8k5_no_empty_feedback_axes failed: before count not reproduced")
    if fix.get("feedback_empty_axis_after_count") != 0:
        raise SystemExit("audit_n8k5_no_empty_feedback_axes failed: empty axes remain")
    if fix.get("feedback_accept_reject_time_not_applicable_count", 0) <= 0:
        raise SystemExit("audit_n8k5_no_empty_feedback_axes failed: not-applicable feedback observation missing")
    print("audit_n8k5_no_empty_feedback_axes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
