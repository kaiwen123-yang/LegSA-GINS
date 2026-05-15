#!/usr/bin/env python3
"""Audit N8K6 did not run degradation matrix."""

# 中文说明：N8K6 不进入 N9B 全量退化矩阵。

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
        if payload.get("degradation_matrix_run") is not False:
            raise SystemExit(f"audit_n8k6_no_degradation_matrix_run failed: {name}")
    print("audit_n8k6_no_degradation_matrix_run passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
