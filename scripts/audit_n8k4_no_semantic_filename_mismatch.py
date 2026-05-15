#!/usr/bin/env python3
"""Audit N8K4 has no semantic filename mismatch."""

# 中文说明：N8K4 修复后不允许 filename 和 semantic_role 再错位。

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
    if fix.get("semantic_filename_mismatch_after_count") != 0:
        raise SystemExit("audit_n8k4_no_semantic_filename_mismatch failed")
    for key in ["yaw_residual_time_mismatch_count", "yaw_wrap_check_mismatch_count", "feedback_accept_reject_timeline_mismatch_count", "reject_all_sanity_mismatch_count"]:
        if fix.get(key) != 0:
            raise SystemExit(f"audit_n8k4_no_semantic_filename_mismatch failed: {key}")
    print("audit_n8k4_no_semantic_filename_mismatch passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
