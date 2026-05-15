#!/usr/bin/env python3
"""Audit N8K formal ablation completeness."""

# 中文说明：正式消融必须完整，不能只生成部分 variant。

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k_by2_formal_ablation_plot_audit import audit_runtime, make_toy_n8k_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k"
            make_toy_n8k_root(root)
            audit_runtime(root)
    else:
        audit_runtime(root)
    print("audit_n8k_formal_ablation_complete passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
