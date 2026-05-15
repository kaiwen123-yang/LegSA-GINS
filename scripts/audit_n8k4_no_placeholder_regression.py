#!/usr/bin/env python3
"""Audit N8K4 did not reintroduce applicable placeholders."""

# 中文说明：N8K4 只允许 documented not-applicable，不允许 applicable placeholder 回归。

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
    coverage = json.loads((root / "N8K4_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json").read_text(encoding="utf-8"))
    if coverage.get("applicable_placeholder_remaining") != 0 or coverage.get("placeholder_remaining") != 0:
        raise SystemExit("audit_n8k4_no_placeholder_regression failed")
    print("audit_n8k4_no_placeholder_regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
