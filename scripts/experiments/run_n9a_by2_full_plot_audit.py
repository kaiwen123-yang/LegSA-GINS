#!/usr/bin/env python3
"""Run N9A BY2 full plot generation and audit.

Runtime paths are command-line inputs only. Tracked files use role aliases such
as <BY2_PLOT_AUDIT_ROOT> and <N9A_FIGURE_OUTPUT_DIR>.

中文说明：runner 只写运行期报告和图像，不进入 N9B，也不修改算法逻辑。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.n9a_by2_full_plot_audit import DEFAULT_N8K_TAG, run_n9a_by2_full_plot_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--by2-plot-root", required=True)
    parser.add_argument("--n8k-tag", default=DEFAULT_N8K_TAG)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    parser.add_argument("--index-output-dir", required=True)
    parser.add_argument("--ppt-output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_n9a_by2_full_plot_audit(
        by2_plot_root=args.by2_plot_root,
        n8k_tag=args.n8k_tag,
        output_dir=args.output_dir,
        figure_output_dir=args.figure_output_dir,
        case_review_dir=args.case_review_dir,
        summary_dir=args.summary_dir,
        index_output_dir=args.index_output_dir,
        ppt_output_dir=args.ppt_output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
