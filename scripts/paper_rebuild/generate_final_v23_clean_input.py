#!/usr/bin/env python3
"""Generate or post-checkpoint-seal one clean-real final_v23 input attempt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.final_v23_clean_input import (
    EXPECTED_RAW_LOCK_SHA256,
    MANIFEST_NAME,
    generate_final_v23_clean_input,
    load_raw_checkpoint,
    seal_clean_input_file_open_audit,
    seal_clean_input_post_raw_checkpoint,
)
from legsa_gins.paper_rebuild.paths import guard_path, load_clean_paths


DEFAULT_CONTRACT = REPO_ROOT / "configs/paper_rebuild/final_v23_parity_contract.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate",
        help="Generate one new attempt using an outer pre-generation 22/22 checkpoint",
    )
    generate.add_argument("--config", required=True, help="Ignored DATA_PATHS local config")
    generate.add_argument(
        "--output-root",
        required=True,
        help="New direct child of <CLEAN_ROOT>/04_PROVIDER_FREEZE named FINAL_V23_CLEAN_*",
    )
    generate.add_argument(
        "--raw-pre-checkpoint",
        required=True,
        help="Outer raw-audit checkpoint JSON; the generator itself never opens trace",
    )
    generate.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    generate.add_argument("--expected-code-commit")
    generate.add_argument("--expected-raw-lock-sha256", default=EXPECTED_RAW_LOCK_SHA256)
    generate.add_argument(
        "--raw-pre-checkpoint-phase",
        choices=("pre_generation", "pre_provider"),
        default="pre_generation",
    )
    generate.add_argument("--max-status-rows", type=int)
    generate.add_argument("--max-raw-rows", type=int)
    generate.add_argument("--max-imu-messages", type=int)

    seal = subparsers.add_parser(
        "seal-post",
        help="Seal an existing generated manifest using an outer post-generation checkpoint",
    )
    seal.add_argument("--config", required=True, help="Ignored DATA_PATHS local config")
    seal.add_argument("--manifest", required=True, help=f"Path to {MANIFEST_NAME}")
    seal.add_argument("--raw-post-checkpoint", required=True)
    seal.add_argument("--expected-raw-lock-sha256", default=EXPECTED_RAW_LOCK_SHA256)
    seal.add_argument(
        "--raw-post-checkpoint-phase",
        choices=("post_generation", "post_provider"),
        default="post_generation",
    )

    file_open = subparsers.add_parser(
        "seal-file-open",
        help="Bind the actual strace openat ledger before post-generation sealing",
    )
    file_open.add_argument("--config", required=True)
    file_open.add_argument("--manifest", required=True)
    file_open.add_argument("--strace", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = load_clean_paths(args.config)
    if args.command == "generate":
        manifest = generate_final_v23_clean_input(
            paths,
            output_root=args.output_root,
            contract_path=args.contract,
            raw_pre_checkpoint=load_raw_checkpoint(args.raw_pre_checkpoint),
            expected_code_commit=args.expected_code_commit,
            expected_raw_lock_sha256=args.expected_raw_lock_sha256,
            max_status_rows=args.max_status_rows,
            max_raw_rows=args.max_raw_rows,
            max_imu_messages=args.max_imu_messages,
            raw_pre_checkpoint_phase=args.raw_pre_checkpoint_phase,
        )
    elif args.command == "seal-post":
        provider_parent = guard_path(
            paths.clean_root / "04_PROVIDER_FREEZE",
            role="CLEAN1R2R1 provider parent",
            allowed_root=paths.clean_root,
        )
        manifest_path = guard_path(
            args.manifest,
            role="CLEAN1R2R1 clean input manifest",
            allowed_root=provider_parent,
            must_exist=True,
            regular_file=True,
        )
        if manifest_path.name != MANIFEST_NAME:
            raise ValueError(f"seal target must be named {MANIFEST_NAME}")
        manifest = seal_clean_input_post_raw_checkpoint(
            manifest_path,
            raw_post_checkpoint=load_raw_checkpoint(args.raw_post_checkpoint),
            raw_hash_lock_path=paths.raw_hash_lock,
            expected_raw_lock_sha256=args.expected_raw_lock_sha256,
            raw_post_checkpoint_phase=args.raw_post_checkpoint_phase,
        )
    else:
        provider_parent = guard_path(
            paths.clean_root / "04_PROVIDER_FREEZE",
            role="CLEAN1R2R1 provider parent",
            allowed_root=paths.clean_root,
        )
        manifest_path = guard_path(
            args.manifest,
            role="CLEAN1R2R1 clean input manifest",
            allowed_root=provider_parent,
            must_exist=True,
            regular_file=True,
        )
        manifest = seal_clean_input_file_open_audit(
            manifest_path,
            strace_path=args.strace,
            raw_root=paths.raw_root,
            code_root=paths.code_root,
        )
    print(
        json.dumps(
            {
                "status": manifest["terminal_status"],
                "stage_id": manifest["stage_id"],
                "protocol_id": manifest["protocol_id"],
                "profile_id": manifest["profile_id"],
                "trace_open_count_during_input_generation": manifest[
                    "trace_open_count_during_input_generation"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
