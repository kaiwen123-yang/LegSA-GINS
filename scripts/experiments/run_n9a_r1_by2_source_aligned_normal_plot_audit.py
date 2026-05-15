#!/usr/bin/env python3
"""Run N9A_R1 BY2 source-aligned normal-condition plot audit.

中文说明：命令行参数接收本地源数据路径，tracked 文件只保留角色别名，不写死绝对路径。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.n9a_r1_by2_source_aligned_normal import build_args, run_n9a_r1_by2_source_aligned_normal_plot_audit


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
    parser.add_argument("--fixposition-imu-data", required=True)
    parser.add_argument("--fixposition-imu-biases", required=True)
    parser.add_argument("--fixposition-imu-temp", required=True)
    parser.add_argument("--ntrip-info", required=True)
    parser.add_argument("--ntrip-latency", required=True)
    parser.add_argument("--corr-raw", required=True)
    parser.add_argument("--tf", required=True)
    parser.add_argument("--tf-static", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--case-review-dir", required=True)
    parser.add_argument("--summary-dir", required=True)
    parser.add_argument("--index-output-dir", required=True)
    parser.add_argument("--ppt-output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    summary = run_n9a_r1_by2_source_aligned_normal_plot_audit(build_args(parse_args()))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
