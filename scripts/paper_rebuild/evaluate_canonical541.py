#!/usr/bin/env python3
"""Evaluate the sealed canonical541 outputs and materialize all analysis tables."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from build_canonical541_manifest import load_local
from legsa_gins.paper_rebuild.canonical541.analysis import materialize_analysis
from legsa_gins.paper_rebuild.canonical541.evaluator import (
    evaluate_unique_outputs, resolve_logical_results,
)
from legsa_gins.paper_rebuild.canonical541.runner import validate_output_seal
from legsa_gins.paper_rebuild.evidence import BY2_TRACE_RELATIVE_PATH
from legsa_gins.paper_rebuild.canonical541.authorization import authorize_operation, validate_attempt_root


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--local-config", required=True)
    command.add_argument("--exact-evaluator", required=True)
    command.add_argument("--jobs", type=int, default=8)
    command.add_argument("--timeout-seconds", type=int, default=900)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    authorize_operation(REPO_ROOT, "offline_evaluator")
    if not 1 <= args.jobs <= 16:
        raise SystemExit("evaluation jobs must be 1..16")
    paths = load_local(Path(args.local_config).resolve(strict=True))
    stage = validate_attempt_root(paths["runtime_root"])
    seal = stage / "11_OUTPUT_SEAL"
    seal_gate = validate_output_seal(seal, raw_root=paths["raw_root"])
    unique = _read_csv(seal / "UNIQUE_RUN_TERMINAL_REGISTRY.csv")
    logical = _read_csv(seal / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv")
    evaluations, evaluation_gate = evaluate_unique_outputs(
        unique_runs=unique, seal_root=seal,
        trace_path=paths["raw_root"] / BY2_TRACE_RELATIVE_PATH,
        exact_evaluator=Path(args.exact_evaluator).resolve(strict=True),
        evaluation_root=stage / "12_OFFLINE_EVALUATION",
        raw_root=paths["raw_root"], timeout_seconds=args.timeout_seconds,
        jobs=args.jobs,
    )
    logical_results = resolve_logical_results(logical, evaluations)
    analysis_gate = materialize_analysis(
        logical_rows=logical_results, unique_rows=unique,
        evaluation_root=stage / "12_OFFLINE_EVALUATION",
        provider_root=paths["provider_root"],
        analysis_root=stage / "13_RESULT_ANALYSIS",
        mechanism_root=stage / "14_MECHANISM_ANALYSIS",
    )
    report = {
        "output_seal": seal_gate,
        "evaluation": evaluation_gate,
        "analysis": analysis_gate,
        "logical_result_count": len(logical_results),
        "trace_used_online": False,
        "passed": evaluation_gate["passed"] and analysis_gate["passed"] and len(logical_results) == 7033,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
