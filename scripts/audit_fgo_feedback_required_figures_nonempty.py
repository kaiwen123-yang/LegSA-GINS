#!/usr/bin/env python3
"""Audit N8H required figures are present and nonempty.

中文说明：确认 N8H 21 张必需图像存在且非空。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n8h_fgo_feedback_visual_validation import audit_toy


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_required_figures_nonempty failed: {message}")


def main() -> int:
    root_value = os.environ.get("N8H_REPORT_OUTPUT_DIR")
    if not root_value:
        audit_toy()
        print("audit_fgo_feedback_required_figures_nonempty passed")
        return 0
    root = Path(root_value)
    manifest_path = root / "N8H_FIGURE_MANIFEST.json"
    coverage_path = root / "N8H_PLOT_DATA_COVERAGE_REPORT.json"
    if not manifest_path.exists() or not coverage_path.exists():
        _fail("missing figure manifest or plot coverage report")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    if manifest.get("required_figure_count") != 21:
        _fail("required figure count is not 21")
    if manifest.get("all_required_figures_nonempty") is not True:
        _fail("manifest reports empty or missing required figure")
    if coverage.get("all_required_figures_nonempty") is not True:
        _fail("coverage reports empty or missing required figure")
    for item in manifest.get("figures", []):
        if item.get("nonempty") is not True:
            _fail(f"empty figure {item.get('relative_path')}")
    print("audit_fgo_feedback_required_figures_nonempty passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
