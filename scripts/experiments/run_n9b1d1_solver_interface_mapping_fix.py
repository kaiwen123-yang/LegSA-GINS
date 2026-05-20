#!/usr/bin/env python3
"""Run N9B1D1 solver interface mapping repair."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1d1_solver_interface_mapping_fix import (  # noqa: E402
    default_n9b1d1_runtime_root,
    run_n9b1d1_solver_interface_mapping_fix,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    parser.add_argument("--skip-wsl-dryrun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_n9b1d1_runtime_root(ROOT)
    result = run_n9b1d1_solver_interface_mapping_fix(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=not args.skip_wsl_dryrun,
    )
    decision = result["decision_report"]
    mapping = result["command_mapping_repair_report"]
    print("N9B1D1 solver interface mapping fix complete")
    print("runtime_root:", runtime_root)
    print("decision_status:", decision["status"])
    print("ready_for_N9B1D_solver_execution:", decision["ready_for_N9B1D_solver_execution"])
    print("ready_for_N9B2_execution:", decision["ready_for_N9B2_execution"])
    print("mapped_rows:", mapping["mapped_rows"])
    print("blocked_requires_real_runner_rows:", mapping["blocked_requires_real_runner_rows"])
    print("validation_status:", result["validation_report"]["status"])
    return 0 if result["validation_report"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
