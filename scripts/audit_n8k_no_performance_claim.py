#!/usr/bin/env python3
"""Audit N8K makes no paper performance claim."""

# 中文说明：所有 N8K 报告必须保持无论文性能宣称。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k_by2_formal_ablation_plot_audit import REQUIRED_REPORTS, make_toy_n8k_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k"
            make_toy_n8k_root(root)
            _audit(root)
    else:
        _audit(root)
    print("audit_n8k_no_performance_claim passed")
    return 0


def _audit(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("paper_performance_claim") is not False or payload.get("outperform_final_v23_claim") is True:
            raise SystemExit(f"audit_n8k_no_performance_claim failed: {name}")


if __name__ == "__main__":
    raise SystemExit(main())
