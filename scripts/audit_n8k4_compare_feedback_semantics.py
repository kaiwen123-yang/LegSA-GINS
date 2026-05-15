#!/usr/bin/env python3
"""Audit N8K4 compare and feedback semantics."""

# 中文说明：horizontal compare 与 reject-all sanity 必须分别落在正确文件名。

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
    fix = json.loads((root / "N8K4_SEMANTIC_FILENAME_FIX_REPORT.json").read_text(encoding="utf-8"))
    if fix.get("compare_horizontal_error_not_applicable_count") != 0:
        raise SystemExit("audit_n8k4_compare_feedback_semantics failed: horizontal compare not-applicable")
    if fix.get("reject_all_sanity_compare_not_applicable_count", 0) <= 0:
        raise SystemExit("audit_n8k4_compare_feedback_semantics failed: reject-all not-applicable not recorded")
    if fix.get("feedback_accept_reject_timeline_applicable_count", 0) <= 0:
        raise SystemExit("audit_n8k4_compare_feedback_semantics failed: feedback timeline applicable missing")
    print("audit_n8k4_compare_feedback_semantics passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
