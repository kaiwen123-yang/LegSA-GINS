#!/usr/bin/env python3
"""Audit N8K plot outputs stay under the BY2 plot audit root."""

# 中文说明：确保 N8K 后续 BY2 绘图不再落到旧绘图验证目录。

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k_by2_formal_ablation_plot_audit import make_toy_n8k_root, report_root


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8k_ablation_plot_outputs_under_by2_audit_root failed: {message}")


def _audit(root: Path) -> None:
    coverage = json.loads((root / "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json").read_text(encoding="utf-8"))
    if coverage.get("all_required_categories_complete") is not True:
        _fail("plot coverage incomplete")
    plot_root = os.environ.get("BY2_PLOT_AUDIT_ROOT")
    figure_root = os.environ.get("N8K_FIGURE_OUTPUT_DIR")
    if plot_root and figure_root and not str(Path(figure_root).resolve()).startswith(str(Path(plot_root).resolve())):
        _fail("figure output dir is outside BY2 plot audit root")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k"
            make_toy_n8k_root(root)
    _audit(root)
    print("audit_n8k_ablation_plot_outputs_under_by2_audit_root passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
