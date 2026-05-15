#!/usr/bin/env python3
"""Audit N8K2 reports no algorithm changes."""

# 中文说明：N8K2 只修图像物化，不改算法数学或 feedback policy。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k2_by2_formal_ablation_real_plot_fix import make_toy_n8k2_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k2"
            make_toy_n8k2_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    decision = json.loads((root / "N8K2_BY2_REAL_PLOT_FIX_DECISION_REPORT.json").read_text(encoding="utf-8"))
    if decision.get("algorithm_changes") is not False or decision.get("no_algorithm_changes") is not True:
        raise SystemExit("audit_n8k2_no_algorithm_change failed")
    print("audit_n8k2_no_algorithm_change passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
