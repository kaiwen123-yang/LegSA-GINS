#!/usr/bin/env python3
"""Evaluate sealed CLEAN2R2A1 outputs with the frozen CLEAN1R2R1 contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean2r2a_analysis import materialize_factorial_analysis
from legsa_gins.paper_rebuild.clean2r2a_evaluator import evaluate_sealed_outputs


def parser() -> argparse.ArgumentParser:
    """Expose the CLI contract so tests can prove forbidden overrides are absent."""

    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--stage-root", required=True)
    command.add_argument("--local-config", required=True)
    command.add_argument("--exact-evaluator", required=True)
    command.add_argument("--timeout-seconds", type=int, default=900)
    return command


def main() -> int:
    args = parser().parse_args()
    evaluation = evaluate_sealed_outputs(
        stage_root=args.stage_root,
        local_config=args.local_config,
        exact_evaluator=args.exact_evaluator,
        timeout_seconds=args.timeout_seconds,
    )
    report = materialize_factorial_analysis(
        evaluation_csv=Path(args.stage_root) / "08_OFFLINE_EVALUATION/CLEAN2R2A1_FACTORIAL_RESULTS.csv",
        output_root=Path(args.stage_root) / "09_FACTORIAL_ANALYSIS",
    )
    print(json.dumps({"evaluation": evaluation, "factorial": report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
