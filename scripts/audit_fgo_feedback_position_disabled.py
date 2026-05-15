#!/usr/bin/env python3
"""Audit N8H primary position-disabled boundary.

中文说明：确认 primary position feedback disabled 且 PVA 统计单独解释。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8h_fgo_feedback_visual_validation import audit_toy


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_position_disabled failed: {message}")


def main() -> int:
    root_value = os.environ.get("N8H_REPORT_OUTPUT_DIR")
    if not root_value:
        audit_toy()
        print("audit_fgo_feedback_position_disabled passed")
        return 0
    path = Path(root_value) / "FGO_FEEDBACK_POSITION_DISABLED_AUDIT_REPORT.json"
    if not path.exists():
        _fail("missing position-disabled audit report")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("status") == "position_disabled_violation":
        _fail("primary position-disabled violation")
    if report.get("primary_position_enabled") is not False:
        _fail("primary position feedback is not disabled")
    if report.get("primary_position_correction_applied_stats_m", {}).get("max", 1.0) > 1.0e-9:
        _fail("primary applied position correction is nonzero")
    if report.get("aggregate_includes_pva") is not True:
        _fail("aggregate does not explain diagnostic PVA contribution")
    print("audit_fgo_feedback_position_disabled passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
