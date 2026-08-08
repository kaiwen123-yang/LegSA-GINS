#!/usr/bin/env python3
"""Run the one-shot CLEAN3R4 AB0000 parity and exact clean-18 readiness gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from build_canonical541_manifest import load_base, load_local
from legsa_gins.paper_rebuild.canonical541.compact_readiness_runner import execute_compact_readiness


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--local-config", required=True)
    command.add_argument("--attempt-root", required=True)
    command.add_argument("--executable", required=True)
    command.add_argument("--code-freeze-commit", required=True)
    command.add_argument("--timeout-seconds", type=int, default=1800)
    command.add_argument("--resume", action="store_true")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    local = Path(args.local_config).resolve(strict=True)
    paths = load_local(local)
    report = execute_compact_readiness(
        repo_root=REPO_ROOT, local_config=local, paths=paths,
        attempt_root=args.attempt_root, executable=args.executable,
        code_freeze_commit=args.code_freeze_commit, base=load_base(paths),
        timeout_seconds=args.timeout_seconds, resume=args.resume,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
