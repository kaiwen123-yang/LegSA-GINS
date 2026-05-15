#!/usr/bin/env python3
"""Audit N8K6 A0 feedback plots are documented not-applicable."""

# 中文说明：A0 的 feedback-specific 图必须是 documented not-applicable。

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.audit_n8k6_a0_feedback_applicability import make_toy_n8k6_root, report_root
from legsa_gins.reporting.by2_feedback_applicability import BASELINE_NOT_APPLICABLE_REASON, FEEDBACK_SPECIFIC_FIGURES


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k6"
            make_toy_n8k6_root(root)
            return _audit(root)
    return _audit(root)


def _audit(root: Path) -> int:
    fix = json.loads((root / "N8K6_A0_FEEDBACK_APPLICABILITY_FIX_REPORT.json").read_text(encoding="utf-8"))
    plot = json.loads((root / "N8K6_A0_FEEDBACK_PLOT_REGENERATION_REPORT.json").read_text(encoding="utf-8"))
    required = {(category, filename) for category, filename in FEEDBACK_SPECIFIC_FIGURES}
    if fix.get("A0_figures_regenerated_count", 0) != len(required):
        raise SystemExit("audit_n8k6_a0_feedback_plots_not_applicable failed: regenerated count")
    if plot.get("documented_not_applicable_count", 0) != len(required):
        raise SystemExit("audit_n8k6_a0_feedback_plots_not_applicable failed: documented NA count")
    if fix.get("A0_effective_feedback_rows_for_plotting_after") != 0:
        raise SystemExit("audit_n8k6_a0_feedback_plots_not_applicable failed: A0 effective rows")
    entries = fix.get("regenerated_entries") or plot.get("figures_regenerated") or []
    seen = {(item.get("category"), item.get("filename")) for item in entries}
    missing = required - seen
    if missing:
        raise SystemExit(f"audit_n8k6_a0_feedback_plots_not_applicable failed: missing {sorted(missing)}")
    for item in entries:
        key = (item.get("category"), item.get("filename"))
        if key not in required:
            continue
        if item.get("documented_not_applicable") is not True or item.get("not_applicable_reason") != BASELINE_NOT_APPLICABLE_REASON:
            raise SystemExit(f"audit_n8k6_a0_feedback_plots_not_applicable failed: not-applicable metadata {key}")
        if item.get("effective_feedback_rows_for_plotting") != 0:
            raise SystemExit(f"audit_n8k6_a0_feedback_plots_not_applicable failed: effective rows {key}")
        if item.get("raw_feedback_rows_detected", 0) <= 0:
            raise SystemExit(f"audit_n8k6_a0_feedback_plots_not_applicable failed: raw rows {key}")
    print("audit_n8k6_a0_feedback_plots_not_applicable passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
