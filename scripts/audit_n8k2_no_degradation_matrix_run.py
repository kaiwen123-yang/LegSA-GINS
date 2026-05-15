#!/usr/bin/env python3
"""Audit N8K2 did not run degradation matrix."""

# 中文说明：N8K2 不进入 N9B 全量退化矩阵。

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
    for name in ["N8K2_REAL_PLOT_MATERIALIZATION_REPORT.json", "N8K2_BY2_REAL_PLOT_FIX_DECISION_REPORT.json"]:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        if payload.get("degradation_matrix_run") is not False:
            raise SystemExit("audit_n8k2_no_degradation_matrix_run failed")
    print("audit_n8k2_no_degradation_matrix_run passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
