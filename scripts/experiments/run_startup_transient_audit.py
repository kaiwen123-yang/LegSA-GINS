#!/usr/bin/env python3
"""Run N4H2F startup transient audit for the visual bundle.

中文说明：只读取 fresh replay error_series 和 summary 做开头瞬态审计；
不删 epoch，不裁剪指标，不修改 solver。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.visualization.startup_transient_audit import (  # noqa: E402
    analyze_startup_transient,
    update_visual_case_review_with_audits,
    write_startup_transient_report,
)


def _default_visual_output_dir() -> Path:
    return Path("/mnt") / "c" / "Users" / "ykw" / "Desktop" / "LegSA-GINS" / "绘图验证"


def run(args: argparse.Namespace) -> dict:
    visual = Path(args.visual_output_dir)
    output = Path(args.output_dir)
    error_series = visual / "evaluation" / "FRESH_REPLAY_ERROR_SERIES.csv"
    summary = visual / "evaluation" / "FRESH_REPLAY_SUMMARY.json"
    report = analyze_startup_transient(error_series, summary)
    write_startup_transient_report(output / "STARTUP_TRANSIENT_AUDIT_REPORT.json", report)
    update_visual_case_review_with_audits(output)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual-output-dir", default=str(_default_visual_output_dir()))
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = run(parse_args(argv))
    print(json.dumps({"startup_transient_visible": report.get("startup_transient_visible")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
