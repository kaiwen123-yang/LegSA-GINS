#!/usr/bin/env python3
"""Freeze the evaluator in an isolated process that never generates provider data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.evaluator import freeze_evaluator_contract
from legsa_gins.paper_rebuild.evidence import BY2_RAW_RELATIVE_PATHS, BY2_TRACE_RELATIVE_PATH, write_read_ledger
from legsa_gins.paper_rebuild.manifest import read_hash_lock, sha256_file
from legsa_gins.paper_rebuild.paths import assert_clean1_path_contract, guard_path, load_clean_paths
from legsa_gins.paper_rebuild.protocol import load_clean1_protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    paths = load_clean_paths(args.config)
    assert_clean1_path_contract(paths, REPO_ROOT)
    protocol = load_clean1_protocol(args.protocol)
    output = guard_path(
        args.output_dir,
        role="CLEAN1 evaluator-freeze output",
        allowed_root=paths.clean_root,
        must_exist=True,
    )
    if sha256_file(paths.raw_hash_lock) != protocol.payload["raw_hash_lock_expected_sha256"]:
        raise RuntimeError("BLOCKED_CLEAN1_BY2_RAW_HASH_OR_ROLE_FAILED")
    lock = read_hash_lock(paths.raw_hash_lock)
    by2_lock = {relative: row for relative, row in lock.items() if row.get("dataset") == "BY2"}
    if len(lock) != protocol.payload["expected_full_lock_rows"] or set(by2_lock) != set(BY2_RAW_RELATIVE_PATHS):
        raise RuntimeError("BLOCKED_CLEAN1_BY2_RAW_HASH_OR_ROLE_FAILED")
    locked_hashes = {relative: str(row.get("sha256") or "") for relative, row in by2_lock.items()}
    frozen = freeze_evaluator_contract(
        args.contract,
        None,
        output,
        reference_relative_path=BY2_TRACE_RELATIVE_PATH,
        expected_reference_sha256=locked_hashes[BY2_TRACE_RELATIVE_PATH],
        reference_point_contract=None,
        reference_frame_contract=None,
        verified_source_hashes=locked_hashes,
    )
    write_read_ledger(
        output / "EVALUATOR_FREEZE_ACTUAL_READ_LEDGER.csv",
        [
            {
                "read_order": 1,
                "path_alias": "<CLEAN_ROOT>",
                "relative_path": paths.raw_hash_lock.resolve(strict=True).relative_to(
                    paths.clean_root.resolve(strict=True)
                ).as_posix(),
                "role": "raw_hash_lock_registry",
                "sha256": sha256_file(paths.raw_hash_lock),
                "reader_component": "paper_rebuild.freeze_evaluator_contract.hash_lock_only",
            },
            {
                "read_order": 2,
                "path_alias": "<CODE_ROOT>",
                "relative_path": "configs/paper_rebuild/evaluator_contract.yaml",
                "role": "tracked_evaluator_contract",
                "sha256": sha256_file(args.contract),
                "reader_component": "paper_rebuild.freeze_evaluator_contract",
            },
        ],
        allowed_roles={"raw_hash_lock_registry", "tracked_evaluator_contract"},
    )
    print(
        json.dumps(
            {
                "ready": frozen.ready,
                "terminal_status": frozen.terminal_status,
                "trace_read_during_freeze": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
