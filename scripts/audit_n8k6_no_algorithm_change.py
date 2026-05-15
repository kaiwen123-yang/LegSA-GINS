#!/usr/bin/env python3
"""Audit N8K6 reports no algorithm change."""

# 中文说明：N8K6 只修 reporting/plot 分类，不改算法。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k6_a0_feedback_applicability import REQUIRED_REPORTS, make_toy_n8k6_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k6"
            make_toy_n8k6_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("algorithm_changes") is not False:
            raise SystemExit(f"audit_n8k6_no_algorithm_change failed: {name}")
    print("audit_n8k6_no_algorithm_change passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
