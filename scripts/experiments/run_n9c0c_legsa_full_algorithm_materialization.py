#!/usr/bin/env python3
"""Run N9C0C LegSA full algorithm materialization and minimum rerun."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9c0c_legsa_full_algorithm_materialization import (  # noqa: E402
    default_full_runtime_root,
    default_stage_root,
    run_n9c0c,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", default=None)
    parser.add_argument("--full-runtime-root", default=None)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--skip-official-eval", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stage_root = Path(args.stage_root) if args.stage_root else default_stage_root(ROOT)
    full_root = Path(args.full_runtime_root) if args.full_runtime_root else default_full_runtime_root(ROOT)
    result = run_n9c0c(
        ROOT,
        stage_root=stage_root,
        full_root=full_root,
        execute=not args.plan_only,
        run_official_eval=not args.skip_official_eval,
    )
    decision = result["decision_report"]
    print("N9C0C LegSA full algorithm materialization complete")
    print("stage_root:", stage_root)
    print("full_runtime_root:", full_root)
    print("decision:", decision["decision"])
    print("ready_for_N9C0D:", decision["ready_for_N9C0D_legsa_full_algorithm_full_matrix_expansion"])
    print("ready_for_N9C1:", decision["ready_for_N9C1_consolidated_figure_generation"])
    print("ready_for_paper_claims:", decision["ready_for_paper_claims"])
    print("recommended_next_stage:", decision["recommended_next_stage"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
