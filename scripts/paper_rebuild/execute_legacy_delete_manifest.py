#!/usr/bin/env python3
"""Dry-run or execute an exact guarded legacy-delete CSV with resume checkpoints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.legacy_delete import (
    dry_run_delete_manifest,
    execute_delete_manifest,
    load_delete_manifest,
    make_delete_roots,
    verify_clean_smoke_gate,
)
from legsa_gins.paper_rebuild.paths import guard_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--paper-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--legacy-freeze-root", required=True)
    parser.add_argument("--code-root", required=True)
    parser.add_argument("--clean-smoke-manifest", required=True)
    parser.add_argument("--log-root", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    verify_clean_smoke_gate(args.clean_smoke_manifest)
    rows = load_delete_manifest(args.manifest)
    roots = make_delete_roots(
        project_root=args.project_root,
        raw_root=args.raw_root,
        paper_root=args.paper_root,
        clean_root=args.clean_root,
        legacy_freeze_root=args.legacy_freeze_root,
        code_root=args.code_root,
    )
    guard_path(
        args.clean_smoke_manifest,
        role="clean smoke deletion gate",
        allowed_root=roots.clean_root,
        must_exist=True,
        regular_file=True,
    )
    log_root = guard_path(args.log_root, role="delete log root", allowed_root=roots.clean_root)
    dry_log = log_root / "DELETE_DRY_RUN_LOG.csv"
    if args.dry_run:
        report, passed = dry_run_delete_manifest(rows, roots, dry_log)
        for row in report:
            if row["delete_allowed"] == "true":
                print(
                    "DELETE_ID={delete_id} EXACT_PATH={exact_path} REALPATH={realpath} "
                    "SIZE={size_bytes} CATEGORY={category} GUARD_RESULT={guard_result}".format(**row)
                )
        print(json.dumps({"status": "PASS" if passed else "FAIL", "rows": len(rows)}, sort_keys=True))
        return 0 if passed else 1
    summary = execute_delete_manifest(rows, roots, log_root=log_root, dry_run_log=dry_log)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["failed_count_this_invocation"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
