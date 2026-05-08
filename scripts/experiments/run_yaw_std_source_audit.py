#!/usr/bin/env python3
"""Run N4H2F yaw STD source audit.

中文说明：区分 input.gnss 观测 yaw_std 与 KF_GINS_STD 状态 yaw std；
不把 yaw_std 误写成 yaw noise injection。
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

from legsa_gins.visualization.startup_transient_audit import update_visual_case_review_with_audits  # noqa: E402
from legsa_gins.visualization.yaw_std_source_audit import (  # noqa: E402
    analyze_yaw_std_source,
    write_yaw_std_source_report,
)


def _default_visual_output_dir() -> Path:
    return Path("/mnt") / "c" / "Users" / "ykw" / "Desktop" / "LegSA-GINS" / "绘图验证"


def run(args: argparse.Namespace) -> dict:
    dual_root = Path(args.dual_root)
    output = Path(args.output_dir)
    report = analyze_yaw_std_source(dual_root / "input.gnss", dual_root / "KF_GINS_STD.txt")
    write_yaw_std_source_report(output / "YAW_STD_SOURCE_AUDIT_REPORT.json", report)
    update_visual_case_review_with_audits(output)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--visual-output-dir", default=str(_default_visual_output_dir()))
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = run(parse_args(argv))
    obs = report.get("observation_yaw_std") or {}
    print(json.dumps({"observation_yaw_std_mean_deg": obs.get("mean")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
