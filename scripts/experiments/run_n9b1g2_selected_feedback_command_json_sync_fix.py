#!/usr/bin/env python3
"""Run N9B1G2 selected-feedback command JSON synchronization fix."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1g2_selected_feedback_command_json_sync_fix import (  # noqa: E402
    default_n9b1g2_runtime_root,
    run_n9b1g2_selected_feedback_command_json_sync_fix,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    parser.add_argument("--skip-wsl-dryrun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_n9b1g2_runtime_root(ROOT)
    result = run_n9b1g2_selected_feedback_command_json_sync_fix(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=not args.skip_wsl_dryrun,
    )
    decision = result["decision_report"]
    validation = result["validation_report"]
    print("N9B1G2 selected-feedback command JSON sync complete")
    print("runtime_root:", runtime_root)
    print("decision_status:", decision["status"])
    print("ready_for_N9B1D_solver_execution:", decision["ready_for_N9B1D_solver_execution"])
    print("ready_for_N9B2_execution:", decision["ready_for_N9B2_execution"])
    print("active_command_rows:", validation["active_command_rows"])
    print("command_json_sync_rows:", validation["command_json_sync_rows"])
    print("wsl_dryrun_rows:", validation["wsl_dryrun_rows"])
    print("feedback_eval_nav_safety_status:", validation["feedback_eval_nav_safety_status"])
    print("validation_status:", validation["status"])
    return 0 if validation["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
