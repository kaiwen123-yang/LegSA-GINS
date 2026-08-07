#!/usr/bin/env python3
"""Run the single authorized CLEAN3 S3 AB0000 byte-parity gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean3_math_repair import (
    Clean3S3Error,
    S3Inputs,
    run_s3_ab0000_parity,
    s3_cli_payload,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    run = commands.add_parser("s3-ab0000-parity")
    run.add_argument("--repo-root", default=str(REPO_ROOT))
    run.add_argument("--clean-root", required=True)
    run.add_argument("--raw-root", required=True)
    run.add_argument("--full-raw-lock", required=True)
    run.add_argument("--by2-raw-lock", required=True)
    run.add_argument("--clean-input-manifest", required=True)
    run.add_argument("--auxiliary-manifest", required=True)
    run.add_argument("--provider-parity-report", required=True)
    run.add_argument("--jobs", type=int, default=2)
    run.add_argument("--timeout-seconds", type=int, default=1800)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = run_s3_ab0000_parity(S3Inputs(
            repo_root=Path(args.repo_root),
            clean_root=Path(args.clean_root),
            raw_root=Path(args.raw_root),
            full_raw_lock=Path(args.full_raw_lock),
            by2_raw_lock=Path(args.by2_raw_lock),
            clean_input_manifest=Path(args.clean_input_manifest),
            auxiliary_manifest=Path(args.auxiliary_manifest),
            provider_parity_report=Path(args.provider_parity_report),
            jobs=args.jobs,
            timeout_seconds=args.timeout_seconds,
        ))
    except Clean3S3Error as exc:
        print(json.dumps({
            "terminal_status": exc.terminal_status,
            "error": str(exc),
            "report_path": str(exc.report_path) if exc.report_path else None,
        }, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(s3_cli_payload(report), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
