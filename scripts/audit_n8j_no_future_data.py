#!/usr/bin/env python3
"""Audit N8J final feedback uses no future data.

中文说明：selected feedback window 必须满足 no-future-data。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8j_feedback_final_validation import make_toy_n8j_root, report_root


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8j_no_future_data failed: {message}")


def _audit(root: Path) -> None:
    policy = json.loads((root / "N8J_SELECTED_FEEDBACK_POLICY_REPORT.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "N8J_FINAL_FEEDBACK_MANIFEST.json").read_text(encoding="utf-8"))
    decision = json.loads((root / "N8J_FEEDBACK_FINAL_VALIDATION_DECISION_REPORT.json").read_text(encoding="utf-8"))
    if policy.get("no_future_data_required") is not True:
        _fail("policy does not require no future data")
    if manifest.get("no_future_data") is not True:
        _fail("manifest no_future_data is not true")
    if decision.get("fgo_feedback_no_future_data") is not True:
        _fail("decision no-future-data flag is not true")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8j"
            make_toy_n8j_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_n8j_no_future_data passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
