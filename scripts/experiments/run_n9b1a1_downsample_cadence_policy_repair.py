#!/usr/bin/env python3
"""Run N9B1A1 downsample cadence policy repair."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_downsample_cadence_policy_repair import (  # noqa: E402
    default_n9b1a1_runtime_root,
    run_downsample_cadence_policy_repair,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", default=None)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_n9b1a1_runtime_root(ROOT)
    matrix_root = Path(args.matrix_root) if args.matrix_root else None
    result = run_downsample_cadence_policy_repair(ROOT, runtime_root=runtime_root, matrix_root=matrix_root, write_outputs=True)
    decision = result["decision_report"]
    print("N9B1A1 downsample cadence policy repair complete")
    print("runtime_root:", runtime_root)
    print("decision_status:", decision["status"])
    print("ready_for_N9B1B_solver_execution:", decision["ready_for_N9B1B_solver_execution"])
    print("ready_for_solver_execution:", decision["ready_for_solver_execution"])
    print("ready_for_N9B2_execution:", decision["ready_for_N9B2_execution"])
    print("blocked_count:", len(decision["blockers"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
