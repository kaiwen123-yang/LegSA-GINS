#!/usr/bin/env python3
"""Audit N8K2 has no placeholders for applicable plots."""

# 中文说明：applicable=True 的数据图 placeholder 数必须为零。

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
    report = json.loads((root / "N8K2_PLACEHOLDER_PLOT_DETECTION_REPORT.json").read_text(encoding="utf-8"))
    if report.get("applicable_placeholder_remaining") != 0 or report.get("fixed_applicable_placeholder_count") != 0:
        raise SystemExit("audit_n8k2_no_placeholder_for_applicable_plots failed")
    print("audit_n8k2_no_placeholder_for_applicable_plots passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
