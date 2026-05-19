#!/usr/bin/env python3
"""Audit N9B1A real pilot input generator outputs and safety boundaries."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_real_pilot_input_generator import (  # noqa: E402
    MATRIX_STEMS,
    PILOT_CASE_IDS,
    REPORT_NAMES,
    default_runtime_root,
    run_real_pilot_input_precheck,
    validate_n9b1a_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", default=None)
    parser.add_argument("--matrix-root", default=None)
    parser.add_argument("--write-runtime", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix_root = Path(args.matrix_root) if args.matrix_root else None
    if args.runtime_root:
        runtime_root = Path(args.runtime_root)
        if args.write_runtime:
            result = run_real_pilot_input_precheck(ROOT, runtime_root=runtime_root, matrix_root=matrix_root, write_outputs=True)
        else:
            result = _load_written(runtime_root)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1a_audit"
            result = run_real_pilot_input_precheck(ROOT, runtime_root=runtime_root, matrix_root=matrix_root, write_outputs=True)
            _audit(result, runtime_root)
            print("audit_n9b1a_real_pilot_input_precheck passed")
            return 0
    _audit(result, runtime_root)
    print("audit_n9b1a_real_pilot_input_precheck passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    result = {
        "degraded_input_index": json.loads((runtime_root / "matrix" / "N9B1A_DEGRADED_INPUT_INDEX.json").read_text(encoding="utf-8")),
        "random_value_index": json.loads((runtime_root / "matrix" / "N9B1A_RANDOM_VALUE_INDEX.json").read_text(encoding="utf-8")),
        "solver_command_plan_index": json.loads((runtime_root / "matrix" / "N9B1A_SOLVER_COMMAND_PLAN_INDEX.json").read_text(encoding="utf-8")),
        "decision_report": json.loads((runtime_root / "reports" / "N9B1A_DECISION_REPORT.json").read_text(encoding="utf-8")),
    }
    return result


def _audit(result: dict, runtime_root: Path) -> None:
    validation = validate_n9b1a_result(
        runtime_root,
        result["degraded_input_index"],
        result["random_value_index"],
        result["solver_command_plan_index"],
        True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1A validation failed: {validation['issues']}")
    for name in REPORT_NAMES:
        payload = json.loads((runtime_root / "reports" / name).read_text(encoding="utf-8"))
        if payload.get("ready_for_solver_execution") is True:
            raise SystemExit(f"{name} incorrectly enables solver execution")
    for stem in MATRIX_STEMS:
        if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
            raise SystemExit(f"missing matrix CSV {stem}")
        if not (runtime_root / "matrix" / f"{stem}.json").is_file():
            raise SystemExit(f"missing matrix JSON {stem}")
    case_ids = {row["case_id"] for row in result["degraded_input_index"]}
    if case_ids != set(PILOT_CASE_IDS):
        raise SystemExit(f"unexpected generated cases: {sorted(case_ids)}")
    if any(row.get("N9B2_full") is not False for row in result["random_value_index"]):
        raise SystemExit("random value manifest must keep N9B2_full=false")
    decision = result["decision_report"]
    if decision["ready_for_solver_execution"] is not False:
        raise SystemExit("ready_for_solver_execution must remain false until N9B1B")
    if decision["ready_for_N9B2_execution"] is not False:
        raise SystemExit("ready_for_N9B2_execution must remain false")


if __name__ == "__main__":
    raise SystemExit(main())
