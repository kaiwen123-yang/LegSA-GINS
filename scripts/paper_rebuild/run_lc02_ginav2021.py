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
    ExecuteResumeExistingR4Options,
    RecoverR4cExecuteOptions,
    RecoverR4cPrepareOptions,
    RecoverR4dExecuteOptions,
    RecoverR4dPrepareOptions,
    ResumeExistingR4Options,
    TransactionError,
    TransactionOptions,
    prepare_resume_existing_r4_from_g3c,
    execute_resume_existing_r4_from_g3c,
    execute_recover_r4b_g3_to_r4c_g4,
    execute_recover_r4c_metadata_to_r4d,
    prepare_recover_r4b_g3_to_r4c_g4,
    prepare_recover_r4c_metadata_to_r4d,
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

    resume = subcommands.add_parser(
        "resume-existing-r4-from-g3c",
        aliases=["resume"],
        help=(
            "hash-lock reusable r4 G0/G1/G2 into one fresh continuation root; "
            "does not execute G3/G4"
        ),
    )
    source = resume.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-r4-root", type=Path)
    source.add_argument(
        "--resume-existing-r4-from-g3c",
        dest="source_r4_root",
        type=Path,
        help="exact source r4 root whose G0/G1/G2 evidence is reused",
    )
    resume.add_argument("--continuation-root", type=Path, required=True)
    resume.add_argument("--matlab-executable", type=Path, required=True)
    resume.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)

    execute_resume = subcommands.add_parser(
        "execute-resume-existing-r4-from-g3c",
        help="execute only the authenticated r4 G3c/G3/conditional-G4 suffix",
    )
    execute_resume.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    execute_resume.add_argument("--paths-config", type=Path, default=DEFAULT_PATHS_CONFIG)
    execute_resume.add_argument("--ginav-root", type=Path, required=True)
    execute_resume.add_argument("--matlab-executable", type=Path, required=True)
    execute_resume.add_argument("--source-r4-root", type=Path, required=True)
    execute_resume.add_argument("--continuation-root", type=Path, required=True)
    execute_resume.add_argument("--probe-timeout-seconds", type=float, default=1800.0)
    execute_resume.add_argument("--c00-timeout-seconds", type=float, default=3600.0)

    recover_prepare = subcommands.add_parser(
        "prepare-recover-r4b-g3-to-r4c-g4",
        help="authenticate frozen r4/r4b and create only the fresh r4c lock",
    )
    recover_prepare.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    recover_prepare.add_argument("--source-r4-root", type=Path, required=True)
    recover_prepare.add_argument("--source-r4b-root", type=Path, required=True)
    recover_prepare.add_argument("--r4c-root", type=Path, required=True)
    recover_prepare.add_argument("--matlab-executable", type=Path, required=True)

    recover_execute = subcommands.add_parser(
        "execute-recover-r4b-g3-to-r4c-g4",
        aliases=["recover-r4b-g3-to-r4c-g4"],
        help="recover exact r4b G3 transport and execute only shared G4",
    )
    recover_execute.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    recover_execute.add_argument("--paths-config", type=Path, default=DEFAULT_PATHS_CONFIG)
    recover_execute.add_argument("--ginav-root", type=Path, required=True)
    recover_execute.add_argument("--matlab-executable", type=Path, required=True)
    recover_execute.add_argument("--source-r4-root", type=Path, required=True)
    recover_execute.add_argument("--source-r4b-root", type=Path, required=True)
    recover_execute.add_argument("--r4c-root", type=Path, required=True)
    recover_execute.add_argument("--c00-timeout-seconds", type=float, default=3600.0)

    metadata_prepare = subcommands.add_parser(
        "prepare-recover-r4c-metadata-to-r4d",
        help="authenticate frozen r4/r4b/r4c and create only an r4d metadata lock",
    )
    metadata_execute = subcommands.add_parser(
        "execute-recover-r4c-metadata-to-r4d",
        help="close native metadata only; never execute MATLAB or G4",
    )
    for entry in (metadata_prepare, metadata_execute):
        entry.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
        entry.add_argument("--source-r4-root", type=Path, required=True)
        entry.add_argument("--source-r4b-root", type=Path, required=True)
        entry.add_argument("--source-r4c-root", type=Path, required=True)
        entry.add_argument("--r4d-root", type=Path, required=True)

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
        elif args.command in {"resume-existing-r4-from-g3c", "resume"}:
            payload = prepare_resume_existing_r4_from_g3c(
                ResumeExistingR4Options(
                    source_r4_root=args.source_r4_root,
                    continuation_root=args.continuation_root,
                    matlab_executable=args.matlab_executable,
                    repository_root=args.repository_root,
                )
            )
        elif args.command == "execute-resume-existing-r4-from-g3c":
            payload = execute_resume_existing_r4_from_g3c(
                ExecuteResumeExistingR4Options(
                    repository_root=args.repository_root,
                    paths_config=args.paths_config,
                    ginav_root=args.ginav_root,
                    matlab_executable=args.matlab_executable,
                    source_r4_root=args.source_r4_root,
                    continuation_root=args.continuation_root,
                    probe_timeout_seconds=args.probe_timeout_seconds,
                    c00_timeout_seconds=args.c00_timeout_seconds,
                )
            )
        elif args.command == "prepare-recover-r4b-g3-to-r4c-g4":
            payload = prepare_recover_r4b_g3_to_r4c_g4(
                RecoverR4cPrepareOptions(
                    repository_root=args.repository_root,
                    source_r4_root=args.source_r4_root,
                    source_r4b_root=args.source_r4b_root,
                    r4c_root=args.r4c_root,
                    matlab_executable=args.matlab_executable,
                )
            )
        elif args.command in {
            "execute-recover-r4b-g3-to-r4c-g4", "recover-r4b-g3-to-r4c-g4"
        }:
            payload = execute_recover_r4b_g3_to_r4c_g4(
                RecoverR4cExecuteOptions(
                    repository_root=args.repository_root,
                    paths_config=args.paths_config, ginav_root=args.ginav_root,
                    matlab_executable=args.matlab_executable,
                    source_r4_root=args.source_r4_root,
                    source_r4b_root=args.source_r4b_root,
                    r4c_root=args.r4c_root,
                    c00_timeout_seconds=args.c00_timeout_seconds,
                )
            )
        elif args.command == "prepare-recover-r4c-metadata-to-r4d":
            payload = prepare_recover_r4c_metadata_to_r4d(
                RecoverR4dPrepareOptions(
                    repository_root=args.repository_root,
                    source_r4_root=args.source_r4_root,
                    source_r4b_root=args.source_r4b_root,
                    source_r4c_root=args.source_r4c_root,
                    r4d_root=args.r4d_root,
                )
            )
        elif args.command == "execute-recover-r4c-metadata-to-r4d":
            payload = execute_recover_r4c_metadata_to_r4d(
                RecoverR4dExecuteOptions(
                    repository_root=args.repository_root,
                    source_r4_root=args.source_r4_root,
                    source_r4b_root=args.source_r4b_root,
                    source_r4c_root=args.source_r4c_root,
                    r4d_root=args.r4d_root,
                )
            )
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
    if args.command in {
        "verify-source", "resume-existing-r4-from-g3c", "resume",
        "prepare-recover-r4b-g3-to-r4c-g4",
    }:
        return 0
    status = str(payload.get("terminal_status") or "")
    scientific_pass = status in {SUCCESS_STATUS, POOR_APPLICABILITY_STATUS}
    transaction_complete = payload.get("transaction_complete") is True
    publication_failed = payload.get("artifact_publication") == "FAILED"
    return 0 if scientific_pass and transaction_complete and not publication_failed else 3


if __name__ == "__main__":
    raise SystemExit(main())
