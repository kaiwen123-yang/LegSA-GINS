#!/usr/bin/env python3
"""Safe convenience wrapper for Canonical541 preparation resume."""

from __future__ import annotations

import argparse

from prepare_canonical541_execution import main as prepare_main


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--local-config", required=True)
    command.add_argument("--executable", required=True)
    command.add_argument("--code-freeze-commit", required=True)
    command.add_argument("--status-interval-seconds", type=float, default=60.0)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return prepare_main([
        "--local-config", args.local_config,
        "--executable", args.executable,
        "--code-freeze-commit", args.code_freeze_commit,
        "--status-interval-seconds", str(args.status_interval_seconds),
        "--prepare-only",
        "--resume-preparation",
        "--stop-before-execution",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
