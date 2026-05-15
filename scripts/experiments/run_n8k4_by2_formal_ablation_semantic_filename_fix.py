#!/usr/bin/env python3
"""Run N8K4 BY2 formal ablation semantic filename fix."""

# 中文说明：N8K4 只修复图像文件名和图像语义错位，不改算法、不运行退化矩阵。

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_semantic_filename_validator import materialize_n8k4_semantic_filename_fix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8k3-root", required=True)
    parser.add_argument("--n8k3-figure-root", required=True)
    parser.add_argument("--n8k3-case-review-root", required=True)
    parser.add_argument("--n8k3-summary-root", required=True)
    parser.add_argument("--n8k2-root", required=True)
    parser.add_argument("--n8k2-figure-root", required=True)
    parser.add_argument("--plot-audit-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    del args.n8k3_case_review_root, args.n8k3_summary_root, args.plot_audit_root
    result = materialize_n8k4_semantic_filename_fix(
        n8k3_root=args.n8k3_root,
        n8k3_figure_root=args.n8k3_figure_root,
        n8k2_root=args.n8k2_root,
        n8k2_figure_root=args.n8k2_figure_root,
        output_dir=args.output_dir,
        figure_output_dir=args.figure_output_dir,
        case_review_dir=args.case_review_dir,
        summary_dir=args.summary_dir,
    )
    summary = {
        "stage": "N8K4",
        "status": result["decision"]["status"],
        "recommended_next_stage": result["decision"]["recommended_next_stage"],
        "semantic_filename_mismatch_before_count": result["audit"]["semantic_filename_mismatch_before_count"],
        "semantic_filename_mismatch_after_count": result["fix"]["semantic_filename_mismatch_after_count"],
        "exact_duplicate_after_count": result["fix"]["exact_duplicate_after_count"],
        "perceptual_duplicate_after_count": result["fix"]["perceptual_duplicate_after_count"],
        "compare_horizontal_error_not_applicable_count": result["fix"]["compare_horizontal_error_not_applicable_count"],
        "reject_all_sanity_compare_not_applicable_count": result["fix"]["reject_all_sanity_compare_not_applicable_count"],
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
