#!/usr/bin/env python3
"""Run N9B1G case-level command rebinding with the formal runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1g_case_level_command_rebind_with_formal_runner import (  # noqa: E402
    default_n9b1g_runtime_root,
    run_n9b1g_case_level_command_rebind_with_formal_runner,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    parser.add_argument("--skip-wsl-dryrun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_n9b1g_runtime_root(ROOT)
    result = run_n9b1g_case_level_command_rebind_with_formal_runner(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=not args.skip_wsl_dryrun,
    )
    decision = result["decision_report"]
    report = result["command_rebind_report"]
    wsl = result["wsl_dryrun_report"]
    print("N9B1G case-level command rebind complete")
    print("runtime_root:", runtime_root)
    print("decision_status:", decision["status"])
    print("ready_for_N9B1D_solver_execution:", decision["ready_for_N9B1D_solver_execution"])
    print("ready_for_N9B2_execution:", decision["ready_for_N9B2_execution"])
    print("source_case_algorithm_rows:", report["source_case_algorithm_rows"])
    print("case_level_command_rows:", report["case_level_command_rows"])
    print("selected_feedback_dependency_command_count:", report["selected_feedback_dependency_command_count"])
    print("wsl_dryrun_rows:", wsl["dryrun_rows"])
    print("validation_status:", result["validation_report"]["status"])
    return 0 if result["validation_report"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
