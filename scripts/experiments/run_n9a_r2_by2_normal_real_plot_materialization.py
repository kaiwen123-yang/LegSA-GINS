#!/usr/bin/env python3
"""Run N9A_R2 BY2 normal real plot materialization.

Runtime paths are passed as CLI arguments. Tracked files keep only role-based
contracts and do not embed local absolute dataset paths.

中文说明：运行时路径只能通过命令行传入，避免把本地绝对路径写进仓库。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.n9a_r2_by2_normal_real_plot_materialization import build_args, run_n9a_r2_by2_normal_real_plot_materialization


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--by2-plot-root", required=True)
    parser.add_argument("--n8k-tag", default="N8K-v0.1-BY2-formal-ablation-plot-audit")
    parser.add_argument("--by2-fixposition-root", required=True)
    parser.add_argument("--gnss1-raw", required=True)
    parser.add_argument("--gnss2-raw", required=True)
    parser.add_argument("--gnss1-status", required=True)
    parser.add_argument("--gnss2-status", required=True)
    parser.add_argument("--trace-truth", required=True)
    parser.add_argument("--go2-body-imu-highlevel", required=True)
    parser.add_argument("--algorithm-output-search-root", action="append", default=[])
    parser.add_argument("--clean-replay-root", required=True)
    parser.add_argument("--dual-final-v23-artifact-root", required=True)
    parser.add_argument("--legsa-run-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    parser.add_argument("--index-output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    summary = run_n9a_r2_by2_normal_real_plot_materialization(build_args(parse_args()))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
