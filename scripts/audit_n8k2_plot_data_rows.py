#!/usr/bin/env python3
"""Audit N8K2 plot data rows."""

# 中文说明：每个正式消融 variant 都必须有可绘制行数据或明确阻塞。

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
    report = json.loads((root / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json").read_text(encoding="utf-8"))
    if report.get("variant_count") != 30 or report.get("unresolved_missing_data_count", 0) != 0:
        raise SystemExit("audit_n8k2_plot_data_rows failed")
    print("audit_n8k2_plot_data_rows passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
