#!/usr/bin/env python3
"""Audit clean smoke lineage, safety flags, hashes, outputs, and path leaks."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.audit import audit_clean_runtime, audit_passed
from legsa_gins.paper_rebuild.paths import load_clean_paths


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "details"])
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, rows: list[dict[str, str]], passed: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Clean smoke result",
        "",
        f"- decision: {'PASS' if passed else 'FAIL'}",
        "- old runtime read: no" if passed else "- old runtime read: audit failed",
        "- paper performance claim: no",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| {row['check']} | {row['status']} | {row['details'].replace('|', '/')} |" for row in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--export-root")
    parser.add_argument("--csv-output")
    parser.add_argument("--markdown-output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = load_clean_paths(args.config)
    rows = audit_clean_runtime(paths, args.runtime_dir, export_root=args.export_root)
    passed = audit_passed(rows)
    if args.csv_output:
        _write_csv(Path(args.csv_output), rows)
    if args.markdown_output:
        _write_markdown(Path(args.markdown_output), rows, passed)
    print(json.dumps({"status": "PASS" if passed else "FAIL", "checks": len(rows)}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
