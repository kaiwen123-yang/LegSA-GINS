#!/usr/bin/env python3
"""Run N4R3 dual_final_v23 official evaluator parity lock.

中文说明：只锁定 evaluator parity；不修改 solver，不复制 artifact 到 tracked 目录。
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

from legsa_gins.evaluation.dual_final_v23_official_parity_lock import lock_dual_final_v23_official_parity  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dual-root", default=None)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = lock_dual_final_v23_official_parity(args.dual_root, output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "evaluator_profile_confirmed": report["evaluator_profile_confirmed"],
                "confirmed_profile_name": report["confirmed_profile_name"],
                "recommended_next_stage": report["recommended_next_stage"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
