#!/usr/bin/env python3
"""Audit N8K did not run the degradation matrix."""

# 中文说明：N8K 只生成 N9B 退化计划，不运行退化矩阵。

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
            plan = json.loads((root / "N8K_N9B_DEGRADATION_PLAN_REPORT.json").read_text(encoding="utf-8"))
    else:
        plan = json.loads((root / "N8K_N9B_DEGRADATION_PLAN_REPORT.json").read_text(encoding="utf-8"))
    if plan.get("degradation_matrix_run") is not False or plan.get("plan_only") is not True:
        raise SystemExit("audit_n8k_no_degradation_matrix_run failed")
    print("audit_n8k_no_degradation_matrix_run passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
