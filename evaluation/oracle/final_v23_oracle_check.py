#!/usr/bin/env python3
"""Boundary oracle for the N1 final_v23-style baseline manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FALSE_FIELDS = [
    "final_v23_is_proposed",
    "proposed_reads_final_v23_output",
    "final_v23_output_substitution",
    "trace_solver_input",
    "trace_used_for_tuning",
    "output_only_correction",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Path to RUN_MANIFEST.json.")
    parser.add_argument("--expected-role", default="baseline", help="Expected algorithm role.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"manifest does not exist: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    if manifest.get("algorithm_role") != args.expected_role:
        failures.append(f"algorithm_role != {args.expected_role}")
    for field in REQUIRED_FALSE_FIELDS:
        if manifest.get(field) is not False:
            failures.append(f"{field} is not false")

    if failures:
        print("final_v23 oracle check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
