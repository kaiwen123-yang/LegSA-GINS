#!/usr/bin/env python3
"""Run N8K5 BY2 formal ablation cross-category semantic fix."""

# 中文说明：N8K5 只修跨 category 图像语义泄漏，不改算法、不运行退化矩阵。

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_cross_category_duplicate_detector import materialize_n8k5_cross_category_fix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8k4-root", required=True)
    parser.add_argument("--n8k4-figure-root", required=True)
    parser.add_argument("--n8k4-case-review-root", required=True)
    parser.add_argument("--n8k4-summary-root", required=True)
    parser.add_argument("--n8k3-root", required=True)
    parser.add_argument("--n8k2-root", required=True)
    parser.add_argument("--plot-audit-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    del args.n8k4_case_review_root, args.n8k4_summary_root
    result = materialize_n8k5_cross_category_fix(
        n8k4_root=args.n8k4_root,
        n8k4_figure_root=args.n8k4_figure_root,
        n8k3_root=args.n8k3_root,
        n8k2_root=args.n8k2_root,
        plot_audit_root=args.plot_audit_root,
        output_dir=args.output_dir,
        figure_output_dir=args.figure_output_dir,
        case_review_dir=args.case_review_dir,
        summary_dir=args.summary_dir,
    )
    summary = {
        "stage": "N8K5",
        "status": result["decision"]["status"],
        "recommended_next_stage": result["decision"]["recommended_next_stage"],
        "global_exact_duplicate_hash_groups_before": result["fix"]["global_exact_duplicate_hash_groups_before"],
        "global_exact_duplicate_hash_groups_after": result["fix"]["global_exact_duplicate_hash_groups_after"],
        "same_variant_cross_category_duplicate_before": result["fix"]["same_variant_cross_category_duplicate_before"],
        "same_variant_cross_category_duplicate_after": result["fix"]["same_variant_cross_category_duplicate_after"],
        "velocity_duplicate_after": result["fix"]["velocity_residual_vs_compare_velocity_duplicate_count_after"],
        "feedback_duplicate_after": result["fix"]["feedback_quality_vs_compare_feedback_delta_duplicate_count_after"],
        "feedback_empty_axis_after_count": result["fix"]["feedback_empty_axis_after_count"],
        "figures_regenerated_count": result["fix"]["figures_regenerated_count"],
        "figures_copied_count": result["fix"]["figures_copied_count"],
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
