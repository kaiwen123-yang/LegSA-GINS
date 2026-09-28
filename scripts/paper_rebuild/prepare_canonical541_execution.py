#!/usr/bin/env python3
"""Resume Canonical541 input preparation and stop before any execution."""

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
from legsa_gins.paper_rebuild.canonical541.authorization import validate_attempt_root
from legsa_gins.paper_rebuild.canonical541.preparation import (
    prepare_only_execution_plan,
    validate_safe_cli_mode,
)
from legsa_gins.paper_rebuild.manifest import sha256_file


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--local-config", required=True)
    command.add_argument("--executable", required=True)
    command.add_argument("--code-freeze-commit", required=True)
    command.add_argument("--prepare-only", action="store_true")
    command.add_argument("--resume-preparation", action="store_true")
    command.add_argument("--stop-before-execution", action="store_true")
    command.add_argument("--status-interval-seconds", type=float, default=60.0)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    validate_safe_cli_mode(
        prepare_only=args.prepare_only,
        resume_preparation=args.resume_preparation,
        stop_before_execution=args.stop_before_execution,
    )
    paths = load_local(Path(args.local_config).resolve(strict=True))
    result = prepare_only_execution_plan(
        repo_root=REPO_ROOT,
        stage_root=validate_attempt_root(paths["runtime_root"]),
        provider_root=paths["provider_root"],
        base_provider_root=paths["base_provider_root"],
        base=load_base(paths),
        executable=args.executable,
        code_freeze_commit=args.code_freeze_commit,
        resume_preparation=args.resume_preparation,
        status_interval_seconds=args.status_interval_seconds,
        local_config_sha256=sha256_file(Path(args.local_config).resolve(strict=True)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
