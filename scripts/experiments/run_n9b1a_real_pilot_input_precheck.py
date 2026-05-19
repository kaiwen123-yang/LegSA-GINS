#!/usr/bin/env python3
"""Run the N9B1A real pilot input generator and WSL bridge precheck."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_real_pilot_input_generator import (  # noqa: E402
    default_runtime_root,
    run_real_pilot_input_precheck,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", default=None)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_runtime_root(ROOT)
    matrix_root = Path(args.matrix_root) if args.matrix_root else None
    result = run_real_pilot_input_precheck(ROOT, runtime_root=runtime_root, matrix_root=matrix_root, write_outputs=True)
    decision = result["decision_report"]
    print("N9B1A real pilot input precheck complete")
    print("runtime_root:", runtime_root)
    print("decision_status:", decision["status"])
    print("ready_for_N9B1B_solver_execution:", decision["ready_for_N9B1B_solver_execution"])
    print("ready_for_solver_execution:", decision["ready_for_solver_execution"])
    print("ready_for_N9B2_execution:", decision["ready_for_N9B2_execution"])
    print("blocked_count:", len(decision["blockers"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
