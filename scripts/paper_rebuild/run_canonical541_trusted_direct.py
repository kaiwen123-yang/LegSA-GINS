#!/usr/bin/env python3
"""Prepare, execute once, and seal the hard-locked trusted-direct matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from build_canonical541_manifest import load_local
from legsa_gins.paper_rebuild.canonical541.trusted_direct import (
    JOBS, SCIENTIFIC_FREEZE, execute_trusted_direct, prepare_trusted_direct,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--local-config", required=True)
    command.add_argument("--executable", required=True)
    command.add_argument("--scientific-freeze", default=SCIENTIFIC_FREEZE)
    command.add_argument("--jobs", type=int, default=JOBS)
    command.add_argument("--timeout-seconds", type=int, default=1800)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.jobs != JOBS:
        raise SystemExit("trusted-direct mode is hard-locked to jobs=12")
    local = Path(args.local_config).resolve(strict=True)
    paths = load_local(local)
    plan, unique, logical = prepare_trusted_direct(
        repo_root=REPO_ROOT, stage_root=paths["runtime_root"],
        base_provider_root=paths["base_provider_root"], executable=args.executable,
        scientific_freeze=args.scientific_freeze,
    )
    unique, seal = execute_trusted_direct(
        repo_root=REPO_ROOT, stage_root=paths["runtime_root"], executable=args.executable,
        scientific_freeze=args.scientific_freeze, raw_root=paths["raw_root"],
        clean_root=paths["clean_root"], unique_rows=unique, logical_rows=logical,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({"plan": plan, "terminal_unique_runs": len(unique), "seal": seal},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
