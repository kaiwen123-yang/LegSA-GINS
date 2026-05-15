#!/usr/bin/env python3
"""Audit N8K reports no solver algorithm change."""

# 中文说明：N8K 是报告和绘图审计阶段，不允许改算法。

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
            matrix = json.loads((root / "N8K_BY2_FORMAL_ABLATION_MATRIX.json").read_text(encoding="utf-8"))
    else:
        matrix = json.loads((root / "N8K_BY2_FORMAL_ABLATION_MATRIX.json").read_text(encoding="utf-8"))
    if matrix.get("algorithm_changes") is not False or matrix.get("feedback_policy_changed") is not False:
        raise SystemExit("audit_n8k_no_algorithm_change failed")
    print("audit_n8k_no_algorithm_change passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
