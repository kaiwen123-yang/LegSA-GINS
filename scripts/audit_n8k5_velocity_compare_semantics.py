#!/usr/bin/env python3
"""Audit N8K5 velocity compare semantics."""

# 中文说明：compare_velocity_error 必须是 compare 语义，不能是 residual 图复制。

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
    if fix.get("compare_velocity_error_semantic_mismatch_after") != 0:
        raise SystemExit("audit_n8k5_velocity_compare_semantics failed: semantic mismatch")
    if fix.get("compare_velocity_error_not_applicable_count", 0) != 0:
        raise SystemExit("audit_n8k5_velocity_compare_semantics failed: unexpected not-applicable")
    if fix.get("velocity_residual_vs_compare_velocity_duplicate_count_after") != 0:
        raise SystemExit("audit_n8k5_velocity_compare_semantics failed: duplicate remains")
    print("audit_n8k5_velocity_compare_semantics passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
