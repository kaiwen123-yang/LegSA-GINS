#!/usr/bin/env python3
"""Audit N8J makes no paper performance claim.

中文说明：N8J 是 BY2 engineering validation，不宣称论文性能或 outperform final_v23。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8j_feedback_final_validation import REQUIRED_REPORTS, make_toy_n8j_root, report_root


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8j_no_performance_claim failed: {message}")


def _audit(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("paper_performance_claim") is not False:
            _fail(f"{name} paper_performance_claim is not false")
        if payload.get("outperform_final_v23_claim") is True:
            _fail(f"{name} claims outperform final_v23")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8j"
            make_toy_n8j_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_n8j_no_performance_claim passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
