#!/usr/bin/env python3
"""Run N9B1C2 selected-feedback same-case mapping."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (  # noqa: E402
    default_n9b1c2_runtime_root,
    generate_same_case_feedback_observations,
    run_n9b1c2_selected_feedback_same_case_mapping,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", "--output-dir", default=None)
    parser.add_argument("--skip-wsl-dryrun", action="store_true")
    parser.add_argument("--generate-feedback-observations", action="store_true")
    parser.add_argument("--case-id", default="")
    parser.add_argument("--baseline-eval-nav", default="")
    parser.add_argument("--gnss-path", default="")
    parser.add_argument("--output-observations", default="")
    parser.add_argument("--output-report", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.generate_feedback_observations:
        required = [args.case_id, args.baseline_eval_nav, args.gnss_path, args.output_observations, args.output_report]
        if not all(required):
            raise SystemExit("--generate-feedback-observations requires case/output/input arguments")
        report = generate_same_case_feedback_observations(
            case_id=args.case_id,
            baseline_eval_nav=Path(args.baseline_eval_nav),
            gnss_path=Path(args.gnss_path),
            output_observations=Path(args.output_observations),
            output_report=Path(args.output_report),
        )
        print("N9B1C2 feedback observations generated")
        print("case_id:", report["case_id"])
        print("feedback_row_count:", report["feedback_row_count"])
        return 0
    runtime_root = Path(args.runtime_root) if args.runtime_root else default_n9b1c2_runtime_root(ROOT)
    result = run_n9b1c2_selected_feedback_same_case_mapping(
        ROOT,
        runtime_root=runtime_root,
        write_outputs=True,
        run_wsl_dryrun=not args.skip_wsl_dryrun,
    )
    decision = result["decision_report"]
    mapping = result["clean_repeat_feedback_policy_report"]
    print("N9B1C2 selected-feedback same-case mapping complete")
    print("runtime_root:", runtime_root)
    print("decision_status:", decision["status"])
    print("ready_for_N9B1D_solver_execution:", decision["ready_for_N9B1D_solver_execution"])
    print("ready_for_N9B2_execution:", decision["ready_for_N9B2_execution"])
    print("mapped_rows:", mapping["mapped_rows"])
    print("blocked_rows:", mapping["blocked_rows"])
    print("validation_status:", result["validation_report"]["status"])
    return 0 if result["validation_report"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
