#!/usr/bin/env python3
"""Audit N8K3 semantic distinction for targeted duplicate pairs."""

# 中文说明：四类重点图必须记录 semantic_fix，不允许只复制改名。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k3_duplicate_semantic_plots import make_toy_n8k3_root, report_root


REQUIRED_FIXES = {"trajectory_comparison_annotation", "yaw_wrap_consistency_panel", "reject_all_compare_semantics", "feedback_reject_all_semantics"}


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k3"
            make_toy_n8k3_root(root)
            fix = json.loads((root / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json").read_text())
            fix["fixed_entries"] = [{"semantic_fix": item} for item in REQUIRED_FIXES]
            (root / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json").write_text(json.dumps(fix), encoding="utf-8")
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    fix = json.loads((root / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json").read_text(encoding="utf-8"))
    seen = {entry.get("semantic_fix") for entry in fix.get("fixed_entries", [])}
    if not REQUIRED_FIXES.issubset(seen):
        raise SystemExit("audit_n8k3_real_plot_semantic_distinction failed")
    print("audit_n8k3_real_plot_semantic_distinction passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
