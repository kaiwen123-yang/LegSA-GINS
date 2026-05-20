#!/usr/bin/env python3
"""Run N9B1C3 execution matrix hygiene and dependency-order lock."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1c3_execution_matrix_hygiene_dependency_order import (  # noqa: E402
    default_n9b1c3_runtime_root,
    run_n9b1c3_execution_matrix_hygiene_dependency_order,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    parser.add_argument("--skip-wsl-path-preflight", action="store_true")
    parser.add_argument("--skip-wsl-dryrun-refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_n9b1c3_runtime_root(ROOT)
    result = run_n9b1c3_execution_matrix_hygiene_dependency_order(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_path_preflight=not args.skip_wsl_path_preflight,
        run_wsl_dryrun_refresh=not args.skip_wsl_dryrun_refresh,
    )
    decision = result["decision_report"]
    hygiene = result["matrix_hygiene_report"]
    preflight = result["wsl_path_preflight_report"]
    print("N9B1C3 execution matrix hygiene dependency-order lock complete")
    print("runtime_root:", runtime_root)
    print("decision_status:", decision["status"])
    print("ready_for_N9B1D_solver_execution:", decision["ready_for_N9B1D_solver_execution"])
    print("ready_for_N9B2_execution:", decision["ready_for_N9B2_execution"])
    print("ready_command_rows:", hygiene["ready_command_rows"])
    print("n9b1d_executable_rows:", hygiene["n9b1d_executable_rows"])
    print("preflight_rows:", preflight["preflight_rows"])
    print("validation_status:", result["validation_report"]["status"])
    return 0 if result["validation_report"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
