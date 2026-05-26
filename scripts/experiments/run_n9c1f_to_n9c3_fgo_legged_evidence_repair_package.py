#!/usr/bin/env python3
"""Run N9C1F-to-N9C3 FGO/legged evidence repair report package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9c1f_to_n9c3_evidence_package import (  # noqa: E402
    REPRESENTATIVE_CASES,
    default_archive_root,
    default_matrix_root,
    default_stage_root,
    run_n9c1f_to_n9c3,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", default=None, help="Stage output root.")
    parser.add_argument("--matrix-root", default=None, help="N9B2 full matrix root.")
    parser.add_argument("--archive-root", default=None, help="USB/archive evidence root. Defaults to LEGSA_GINS_ARCHIVE_ROOT, BY2_ARCHIVE_ROOT, or the workspace root.")
    parser.add_argument("--cases", default=",".join(REPRESENTATIVE_CASES), help="Comma-separated representative cases.")
    parser.add_argument("--no-solver-rerun", action="store_true", help="Required; this runner refuses solver reruns.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.no_solver_rerun:
        raise SystemExit("--no-solver-rerun is required for this report-only stage")
    cases = [item.strip() for item in args.cases.split(",") if item.strip()]
    result = run_n9c1f_to_n9c3(
        ROOT,
        stage_root=Path(args.runtime_root) if args.runtime_root else default_stage_root(ROOT),
        matrix_root=Path(args.matrix_root) if args.matrix_root else default_matrix_root(ROOT),
        archive_root=Path(args.archive_root) if args.archive_root else default_archive_root(ROOT),
        representative_cases=cases,
        no_solver_rerun=True,
    )
    decision = result["decision"]
    print("N9C1F-to-N9C3 evidence repair/report package complete")
    print("stage_root:", result["stage_root"])
    print("evidence_root:", result["evidence_root"])
    print("replot_root:", result["replot_root"])
    print("n9c3_root:", result["n9c3_root"])
    print("status:", decision["status"])
    print("ready_for_N9D_claim_boundary_review:", decision["ready_for_N9D_claim_boundary_review"])
    print("ready_for_paper_claims:", decision["ready_for_paper_claims"])
    print("recommended_next_stage:", decision["recommended_next_stage"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
