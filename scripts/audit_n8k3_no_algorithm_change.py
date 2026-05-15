#!/usr/bin/env python3
"""Audit N8K3 reports no algorithm change."""

# 中文说明：N8K3 是绘图修复，不改 solver 或 feedback policy。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k3_duplicate_semantic_plots import make_toy_n8k3_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k3"
            make_toy_n8k3_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    decision = json.loads((root / "N8K3_BY2_FORMAL_ABLATION_DUPLICATE_PLOT_FIX_DECISION_REPORT.json").read_text(encoding="utf-8"))
    if decision.get("algorithm_changes") is not False or decision.get("no_algorithm_changes") is not True:
        raise SystemExit("audit_n8k3_no_algorithm_change failed")
    print("audit_n8k3_no_algorithm_change passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
