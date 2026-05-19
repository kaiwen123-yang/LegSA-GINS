#!/usr/bin/env python3
"""Audit N9B0B degradation runner precheck boundaries."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_degradation_runner_precheck import (
    FORBIDDEN_EXECUTION_OUTPUT_NAMES,
    discover_cleaned_matrix_root,
    run_dryrun_precheck,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", default=None)
    parser.add_argument("--runtime-root", default=None)
    parser.add_argument("--write-runtime", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix_root = Path(args.matrix_root) if args.matrix_root else discover_cleaned_matrix_root(ROOT)
    if args.runtime_root:
        runtime_root = Path(args.runtime_root)
        result = run_dryrun_precheck(matrix_root=matrix_root, runtime_root=runtime_root, write_outputs=args.write_runtime)
        _audit_result(result, runtime_root if args.write_runtime else None)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b0b_audit"
            result = run_dryrun_precheck(matrix_root=matrix_root, runtime_root=runtime_root, write_outputs=True)
            _audit_result(result, runtime_root)
    print("audit_n9b0b_degradation_runner_precheck passed")
    return 0


def _audit_result(result: dict, runtime_root: Path | None) -> None:
    validation = result["validation"]
    safety = result["safety_gate_report"]
    decision = result["decision_report"]
    if validation["status"] != "pass":
        raise SystemExit(f"source matrix validation failed: {validation['issues']}")
    if safety["status"] != "pass":
        raise SystemExit(f"safety gate failed: {safety['issues']}")
    if decision["ready_for_N9B_execution"] is not False:
        raise SystemExit("ready_for_N9B_execution must remain false")
    if not safety["dryrun_only"] or not safety["not_executed"] or not safety["no_solver_run"]:
        raise SystemExit("dry-run safety flags are not all set")
    if runtime_root is not None:
        forbidden_names = set(FORBIDDEN_EXECUTION_OUTPUT_NAMES)
        for path in runtime_root.rglob("*"):
            if any(path.name.startswith(name) for name in forbidden_names):
                raise SystemExit(f"forbidden runtime output generated: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
