#!/usr/bin/env python3
"""Audit N8K6 feedback applicability follows variant spec roles."""

# 中文说明：feedback 适用性以消融 variant 语义角色为准。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k6_a0_feedback_applicability import FEEDBACK_APPLICABLE_AFTER, make_toy_n8k6_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k6"
            make_toy_n8k6_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    fix = json.loads((root / "N8K6_A0_FEEDBACK_APPLICABILITY_FIX_REPORT.json").read_text(encoding="utf-8"))
    applicable = set(fix.get("feedback_applicable_variants_after", []))
    if "A0_source_backed_ekf_baseline" in applicable:
        raise SystemExit("audit_n8k6_feedback_applicability_by_spec failed: A0 applicable")
    missing = set(FEEDBACK_APPLICABLE_AFTER) - applicable
    if missing:
        raise SystemExit(f"audit_n8k6_feedback_applicability_by_spec failed: missing {sorted(missing)}")
    not_applicable = set(fix.get("feedback_not_applicable_variants_after", []))
    if "A0_source_backed_ekf_baseline" not in not_applicable:
        raise SystemExit("audit_n8k6_feedback_applicability_by_spec failed: A0 not in NA")
    print("audit_n8k6_feedback_applicability_by_spec passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
