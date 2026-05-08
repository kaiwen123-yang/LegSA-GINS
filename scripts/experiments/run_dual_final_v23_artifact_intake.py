#!/usr/bin/env python3
"""Run N4R3 manual dual_final_v23 artifact intake.

中文说明：只校验仓库外 artifact root，不复制到 tracked 目录，不提交 artifact 文件。
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

from legsa_gins.source_audit.dual_final_v23_artifact_intake import run_dual_artifact_intake  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dual-root", default=None)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_dual_artifact_intake(args.dual_root, output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "dual_artifact_intake_status": report["dual_artifact_intake_status"],
                "dual_final_v23_confirmed": report["dual_final_v23_confirmed"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
