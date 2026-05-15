#!/usr/bin/env python3
"""Audit N8K6 has no empty feedback-axis regressions."""

# 中文说明：无 feedback 的图不能画空坐标轴伪装适用。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k6_a0_feedback_applicability import make_toy_n8k6_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k6"
            make_toy_n8k6_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    coverage = json.loads((root / "N8K6_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json").read_text(encoding="utf-8"))
    if coverage.get("feedback_empty_axis_after") != 0:
        raise SystemExit("audit_n8k6_no_empty_feedback_axes failed")
    print("audit_n8k6_no_empty_feedback_axes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
