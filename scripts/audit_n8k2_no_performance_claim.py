#!/usr/bin/env python3
"""Audit N8K2 makes no performance claim."""

# 中文说明：N8K2 图像修复不产生论文性能 claim 或 outperform claim。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k2_by2_formal_ablation_real_plot_fix import REQUIRED_REPORTS, make_toy_n8k2_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k2"
            make_toy_n8k2_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    for name in REQUIRED_REPORTS:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("paper_performance_claim") is not False or payload.get("outperform_final_v23_claim") is True:
            raise SystemExit("audit_n8k2_no_performance_claim failed")
    print("audit_n8k2_no_performance_claim passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
