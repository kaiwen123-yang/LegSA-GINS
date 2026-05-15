#!/usr/bin/env python3
"""Audit N8K4 yaw residual and wrap plot semantics."""

# 中文说明：yaw residual 和 yaw wrap check 是两个不同语义图。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8k4_semantic_filename_alignment import make_toy_n8k4_root, report_root


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k4"
            make_toy_n8k4_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    fix = json.loads((root / "N8K4_SEMANTIC_FILENAME_FIX_REPORT.json").read_text(encoding="utf-8"))
    if fix.get("yaw_residual_time_mismatch_count") != 0 or fix.get("yaw_wrap_check_mismatch_count") != 0:
        raise SystemExit("audit_n8k4_yaw_plot_semantics failed")
    roles = {(entry.get("category"), entry.get("filename")): entry.get("semantic_role") for entry in fix.get("fixed_entries", [])}
    if roles.get(("04_attitude", "yaw_residual_time.png")) not in {None, "yaw_residual_time_series"}:
        raise SystemExit("audit_n8k4_yaw_plot_semantics failed: residual role")
    print("audit_n8k4_yaw_plot_semantics passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
