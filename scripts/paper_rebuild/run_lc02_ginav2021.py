#!/usr/bin/env python3
"""Verify or execute the bounded exact-official GINav 2021 LC02 route."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.constants import (
    POOR_APPLICABILITY_STATUS,
    SUCCESS_STATUS,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.source import (
    SourceIdentityError,
    verify_source_identity,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.transaction import (
    TransactionError,
    TransactionOptions,
    run_transaction,
)


DEFAULT_PATHS_CONFIG = (
    REPOSITORY_ROOT / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    subcommands = command.add_subparsers(dest="command", required=True)

    verify = subcommands.add_parser(
        "verify-source", help="read-only pinned official source identity check"
    )
    verify.add_argument("--ginav-root", type=Path, required=True)

    execute = subcommands.add_parser(
        "execute", help="explicitly launch the authorized gate-ordered transaction"
    )
    execute.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    execute.add_argument("--paths-config", type=Path, default=DEFAULT_PATHS_CONFIG)
    execute.add_argument("--ginav-root", type=Path, required=True)
    execute.add_argument("--matlab-executable", type=Path, required=True)
    execute.add_argument("--libarchive-path", type=Path, required=True)
    execute.add_argument("--scratch-root", type=Path, required=True)
    execute.add_argument("--stage-root", type=Path, required=True)
    execute.add_argument("--paper-root", type=Path, required=True)
    execute.add_argument("--legacy-freeze-root", type=Path, required=True)
    execute.add_argument("--no-publish", action="store_true")
    execute.add_argument("--sample-timeout-seconds", type=float, default=3600.0)
    execute.add_argument("--probe-timeout-seconds", type=float, default=1800.0)
    execute.add_argument("--c00-timeout-seconds", type=float, default=3600.0)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "verify-source":
            payload = verify_source_identity(args.ginav_root)
        else:
            payload = run_transaction(
                TransactionOptions(
                    repository_root=args.repository_root,
                    paths_config=args.paths_config,
                    ginav_root=args.ginav_root,
                    matlab_executable=args.matlab_executable,
                    libarchive_path=args.libarchive_path,
                    scratch_root=args.scratch_root,
                    destination_stage_root=args.stage_root,
                    paper_root=args.paper_root,
                    legacy_freeze_root=args.legacy_freeze_root,
                    publish=not args.no_publish,
                    sample_timeout_seconds=args.sample_timeout_seconds,
                    probe_timeout_seconds=args.probe_timeout_seconds,
                    c00_timeout_seconds=args.c00_timeout_seconds,
                )
            )
    except (OSError, ValueError, SourceIdentityError, TransactionError) as exc:
        print(json.dumps({"error": str(exc), "pass": False}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if args.command == "verify-source":
        return 0
    status = str(payload.get("terminal_status") or "")
    scientific_pass = status in {SUCCESS_STATUS, POOR_APPLICABILITY_STATUS}
    transaction_complete = payload.get("transaction_complete") is True
    publication_failed = payload.get("artifact_publication") == "FAILED"
    return 0 if scientific_pass and transaction_complete and not publication_failed else 3


if __name__ == "__main__":
    raise SystemExit(main())
