#!/usr/bin/env python3
"""Run N8K BY2 formal ablation and ablation plot audit.

Runtime paths are command-line inputs only. Tracked files use role aliases.
"""

# 中文说明：命令行路径只作为 runtime 参数使用，不写入 tracked 配置。

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_formal_ablation_runner import run_n8k_formal_ablation_plot_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--n8f1-root", required=True)
    parser.add_argument("--n8i-root", required=True)
    parser.add_argument("--n8j-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--plot-audit-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    del args.clean_root, args.dual_root, args.build_dir, args.exe
    summary = run_n8k_formal_ablation_plot_audit(
        previous_roots={
            "n5b": args.n5b_root,
            "n6b": args.n6b_root,
            "n7c6": args.n7c6_root,
            "n8f1": args.n8f1_root,
            "n8i": args.n8i_root,
            "n8j": args.n8j_root,
        },
        plot_audit_root=args.plot_audit_root,
        output_dir=args.output_dir,
        figure_output_dir=args.figure_output_dir,
        case_review_dir=args.case_review_dir,
        summary_dir=args.summary_dir,
        allow_run=args.allow_run,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
