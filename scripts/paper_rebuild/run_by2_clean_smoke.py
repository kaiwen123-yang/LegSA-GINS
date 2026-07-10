#!/usr/bin/env python3
"""Run one bounded BY2 clean smoke through the independent paper runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.runner import APPROVED_METHODS, CleanPaperRunner


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Ignored DATA_PATHS.local.yaml")
    parser.add_argument(
        "--method",
        choices=sorted(APPROVED_METHODS),
        default="basic_dual_yaw_EKF",
        help="CLEAN0 minimum is basic_dual_yaw_EKF",
    )
    parser.add_argument("--run-id", help="Safe leaf name under clean runtime/smoke")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Remove and regenerate only the exact selected clean smoke directory",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Write and print the fresh command without launching the solver",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner = CleanPaperRunner(args.config)
    if args.prepare_only:
        prepared = runner.prepare(method=args.method, run_id=args.run_id, replace=False)
        print(
            json.dumps(
                {
                    "status": "PREPARED_NOT_RUN",
                    "method": prepared.method,
                    "command": "<PORT_CORE_EXE> --config <CLEAN_RUNTIME_CONFIG> --output-dir <CLEAN_SMOKE_OUTPUT>",
                    "config_hash_pending_run": True,
                },
                sort_keys=True,
            )
        )
        return 0
    manifest = runner.run(
        method=args.method,
        run_id=args.run_id,
        timeout_seconds=args.timeout_seconds,
        replace=args.replace,
    )
    print(json.dumps({"status": manifest["terminal_status"], "run_id": manifest["run_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
