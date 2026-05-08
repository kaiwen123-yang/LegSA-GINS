#!/usr/bin/env python3
"""Run diagnostic yaw input variant matrix.

中文说明：variant 输出只写 runtime output dir；trace yaw 只用于诊断，不作为 solver input。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.yaw_input_variant_matrix import (  # noqa: E402
    build_yaw_input_variant_matrix,
    load_trace_yaw_from_replay,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-gnss", required=True)
    parser.add_argument("--replay-nav")
    parser.add_argument("--error-series")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    trace_rows = []
    if args.replay_nav and args.error_series and Path(args.replay_nav).exists() and Path(args.error_series).exists():
        trace_rows = load_trace_yaw_from_replay(args.replay_nav, args.error_series)
    out = Path(args.output_dir)
    report = build_yaw_input_variant_matrix(args.input_gnss, trace_yaw_rows=trace_rows, output_dir=out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "YAW_INPUT_VARIANT_MATRIX_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"variant_count": report["variant_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
