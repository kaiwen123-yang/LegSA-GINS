#!/usr/bin/env python3
"""Run N9B1F real LegSA algorithm runner mapping and normal parity gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import (  # noqa: E402
    default_n9b1f_runtime_root,
    run_n9b1f_real_legsa_algorithm_runner,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    parser.add_argument("--allow-normal-run", action="store_true")
    parser.add_argument("--skip-official-eval", action="store_true")
    parser.add_argument("--skip-wsl-dryrun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_n9b1f_runtime_root(ROOT)
    result = run_n9b1f_real_legsa_algorithm_runner(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        execute_normal_parity=args.allow_normal_run,
        run_official_eval=not args.skip_official_eval,
        run_wsl_dryrun=not args.skip_wsl_dryrun,
    )
    decision = result["decision_report"]
    print("N9B1F real LegSA algorithm runner complete")
    print("runtime_root:", runtime_root)
    print("decision_status:", decision["status"])
    print("ready_for_N9B1D_solver_execution:", decision["ready_for_N9B1D_solver_execution"])
    print("ready_for_N9B2_execution:", decision["ready_for_N9B2_execution"])
    print("parity_passed_algorithms:", ",".join(decision["parity_passed_algorithms"]) or "none")
    print("blocked_algorithm_count:", len(decision["blocked_algorithms"]))
    print("validation_status:", result["validation_report"]["status"])
    return 0 if result["validation_report"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
