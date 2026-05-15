#!/usr/bin/env python3
"""Run N8K6 targeted A0 feedback applicability blocker fix."""

# 中文说明：只修 A0 no-feedback baseline 的 feedback 绘图适用性分类，不改算法。

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_feedback_applicability import materialize_n8k6_a0_feedback_applicability_fix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8k5-root", required=True)
    parser.add_argument("--n8k5-figure-root", required=True)
    parser.add_argument("--n8k5-case-review-root", required=True)
    parser.add_argument("--n8k5-summary-root", required=True)
    parser.add_argument("--plot-audit-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = materialize_n8k6_a0_feedback_applicability_fix(
        n8k5_root=Path(args.n8k5_root),
        n8k5_figure_root=Path(args.n8k5_figure_root),
        n8k5_case_review_root=Path(args.n8k5_case_review_root),
        n8k5_summary_root=Path(args.n8k5_summary_root),
        plot_audit_root=Path(args.plot_audit_root),
        output_dir=Path(args.output_dir),
        figure_output_dir=Path(args.figure_output_dir),
        case_review_dir=Path(args.case_review_dir),
        summary_dir=Path(args.summary_dir),
    )
    decision = result["decision"]
    fix = result["fix"]
    print("N8K6 A0 feedback applicability fix complete")
    print("decision:", decision.get("status"))
    print("recommended_next_stage:", decision.get("recommended_next_stage"))
    print("A0 feedback applicable before/after:", fix.get("A0_feedback_applicable_before"), fix.get("A0_feedback_applicable_after"))
    print("A0 effective feedback rows after:", fix.get("A0_effective_feedback_rows_for_plotting_after"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
