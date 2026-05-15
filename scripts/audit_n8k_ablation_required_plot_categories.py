#!/usr/bin/env python3
"""Audit N8K required plot categories 01-14."""

# 中文说明：检查 01 到 14 类消融图像是否全部覆盖。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k_by2_formal_ablation_plot_audit import make_toy_n8k_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k"
            make_toy_n8k_root(root)
            coverage = json.loads((root / "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json").read_text(encoding="utf-8"))
    else:
        coverage = json.loads((root / "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json").read_text(encoding="utf-8"))
    if coverage.get("required_category_count") != 14 or coverage.get("missing_count") != 0:
        raise SystemExit("audit_n8k_ablation_required_plot_categories failed")
    print("audit_n8k_ablation_required_plot_categories passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
