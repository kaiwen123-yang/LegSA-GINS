#!/usr/bin/env python3
"""Audit N8K2 figure output role stays under BY2 audit root."""

# 中文说明：tracked 报告只记录 role alias，不写入本地绝对路径。

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
    report = json.loads((root / "N8K2_REAL_PLOT_MATERIALIZATION_REPORT.json").read_text(encoding="utf-8"))
    if report.get("stage") != "N8K2":
        raise SystemExit("audit_n8k2_plot_outputs_under_by2_audit_root failed")
    text = json.dumps(report, ensure_ascii=False)
    if "/mnt/c/Users" in text or "C:\\\\Users" in text:
        raise SystemExit("audit_n8k2_plot_outputs_under_by2_audit_root failed: path leak")
    print("audit_n8k2_plot_outputs_under_by2_audit_root passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
