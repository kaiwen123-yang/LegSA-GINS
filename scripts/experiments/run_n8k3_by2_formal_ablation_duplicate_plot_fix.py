#!/usr/bin/env python3
"""Run N8K3 BY2 formal ablation duplicate plot fix."""

# 中文说明：N8K3 只修复同类图 exact duplicate，不改算法、不运行退化矩阵。

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_duplicate_semantic_plot_detector import materialize_n8k3_duplicate_fix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8k2-root", required=True)
    parser.add_argument("--n8k2-figure-root", required=True)
    parser.add_argument("--n8k2-case-review-root", required=True)
    parser.add_argument("--n8k2-summary-root", required=True)
    parser.add_argument("--plot-audit-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    del args.n8k2_case_review_root, args.n8k2_summary_root, args.plot_audit_root
    result = materialize_n8k3_duplicate_fix(
        n8k2_root=args.n8k2_root,
        n8k2_figure_root=args.n8k2_figure_root,
        output_dir=args.output_dir,
        figure_output_dir=args.figure_output_dir,
        case_review_dir=args.case_review_dir,
        summary_dir=args.summary_dir,
    )
    summary = {
        "stage": "N8K3",
        "status": result["decision"]["status"],
        "recommended_next_stage": result["decision"]["recommended_next_stage"],
        "blocking_duplicate_patterns_before": result["audit"]["blocking_duplicate_count_before"],
        "same_category_exact_duplicate_remaining": result["decision"]["same_category_exact_duplicate_remaining"],
        "perceptual_duplicate_after_count": result["decision"]["perceptual_duplicate_after_count"],
        "figures_regenerated_count": result["fix"]["figures_regenerated_count"],
        "derived_data_labels_count": result["fix"]["derived_data_labels_count"],
        "not_applicable_count": result["fix"]["not_applicable_count"],
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
