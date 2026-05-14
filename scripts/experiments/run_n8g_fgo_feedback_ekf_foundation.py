#!/usr/bin/env python3
"""Run N8G FGO feedback EKF foundation.

中文说明：所有本地绝对路径只能作为 runtime 参数进入；tracked 脚本只记录 role
alias 和边界，不提交 runtime outputs/figures。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_runner import run_n8g_feedback_foundation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n8f-root", required=True)
    parser.add_argument("--n8f1-root", required=True)
    parser.add_argument("--n8e-root", required=True)
    parser.add_argument("--n8d-root", required=True)
    parser.add_argument("--n8c3-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N8G runtime generation")
    run_n8g_feedback_foundation(
        n8f_root=args.n8f_root,
        n8f1_root=args.n8f1_root,
        n8e_root=args.n8e_root,
        n8d_root=args.n8d_root,
        n8c3_root=args.n8c3_root,
        n7c6_root=args.n7c6_root,
        clean_root=args.clean_root,
        dual_root=args.dual_root,
        build_dir=args.build_dir,
        exe=args.exe,
        output_dir=args.output_dir,
        figure_output_dir=args.figure_output_dir,
        allow_run=args.allow_run,
        cwd=ROOT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
