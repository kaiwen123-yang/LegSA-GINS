#!/usr/bin/env python3
"""Audit N9B0C toy-only pilot generator precheck outputs and boundaries."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_degradation_pilot_generators import (  # noqa: E402
    FORBIDDEN_EXECUTION_OUTPUT_NAMES,
    PILOT_CASE_IDS,
    discover_cleaned_matrix_root,
    run_pilot_generator_precheck,
    validate_pilot_precheck_result,
)


REQUIRED_REPORTS = [
    "N9B0C_GENERATOR_IMPLEMENTATION_REPORT.json",
    "N9B0C_RANDOMNESS_TOY_VALIDATION_REPORT.json",
    "N9B0C_APPLICABILITY_ROUTING_REPORT.json",
    "N9B0C_PILOT_READINESS_REPORT.json",
    "N9B0C_SAFETY_GATE_REPORT.json",
    "N9B0C_DECISION_REPORT.json",
]

REQUIRED_MATRIX_STEMS = [
    "N9B0C_GENERATOR_CAPABILITY_MATRIX",
    "N9B0C_N9B1_PILOT_READY_MATRIX",
    "N9B0C_TOY_RANDOM_VALUE_MANIFEST",
    "N9B0C_APPLICABILITY_ROUTING_CHECK",
    "N9B0C_BLOCKED_ITEMS",
]

REQUIRED_SUMMARIES = [
    "n9b0c_generator_implementation.md",
    "n9b0c_pilot_readiness.md",
    "n9b0c_safety_gate.md",
    "n9b0c_next_stage_recommendation.md",
]


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
        result = run_pilot_generator_precheck(matrix_root=matrix_root, runtime_root=runtime_root, write_outputs=args.write_runtime)
        _audit_result(result, runtime_root if args.write_runtime else None)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b0c_audit"
            result = run_pilot_generator_precheck(matrix_root=matrix_root, runtime_root=runtime_root, write_outputs=True)
            _audit_result(result, runtime_root)
    print("audit_n9b0c_pilot_generator_precheck passed")
    return 0


def _audit_result(result: dict, runtime_root: Path | None) -> None:
    validation = validate_pilot_precheck_result(result, runtime_root)
    if validation["status"] != "pass":
        raise SystemExit(f"N9B0C validation failed: {validation['issues']}")
    if result["decision_report"]["ready_for_N9B_execution"] is not False:
        raise SystemExit("ready_for_N9B_execution must remain false")
    if result["decision_report"]["ready_for_N9B1_execution"] is not True:
        raise SystemExit("ready_for_N9B1_execution must be true after N9B0C passes")
    case_ids = [row["case_id"] for row in result["generator_capability_matrix"]]
    if case_ids != PILOT_CASE_IDS:
        raise SystemExit(f"unexpected pilot case order: {case_ids}")
    if any(not row["ready_for_N9B1_execution"] for row in result["n9b1_pilot_ready_matrix"]):
        raise SystemExit("all pilot rows must be ready_for_N9B1_execution=true")
    if any(not row.get("hash_sha256") for row in result["toy_random_value_manifest"]):
        raise SystemExit("toy random manifest rows must record hash_sha256")
    if runtime_root is not None:
        _audit_runtime_files(runtime_root)


def _audit_runtime_files(runtime_root: Path) -> None:
    for name in REQUIRED_REPORTS:
        payload = json.loads((runtime_root / "reports" / name).read_text(encoding="utf-8"))
        if payload.get("ready_for_N9B_execution") is not False:
            raise SystemExit(f"{name} does not keep ready_for_N9B_execution=false")
        if payload.get("toy_only") is not True:
            raise SystemExit(f"{name} missing toy_only=true")
    for stem in REQUIRED_MATRIX_STEMS:
        if not (runtime_root / "matrix" / f"{stem}.json").is_file():
            raise SystemExit(f"missing matrix JSON {stem}")
        if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
            raise SystemExit(f"missing matrix CSV {stem}")
    for name in REQUIRED_SUMMARIES:
        text = (runtime_root / "summary" / name).read_text(encoding="utf-8")
        if "ready_for_N9B_execution=false" not in text:
            raise SystemExit(f"{name} missing ready_for_N9B_execution=false")
    forbidden_prefixes = set(FORBIDDEN_EXECUTION_OUTPUT_NAMES)
    forbidden_suffixes = {".npy", ".npz", ".png", ".pdf", ".svg", ".jpg", ".jpeg"}
    for path in runtime_root.rglob("*"):
        if not path.is_file():
            continue
        if any(path.name.startswith(prefix) for prefix in forbidden_prefixes):
            raise SystemExit(f"forbidden execution output generated: {path}")
        if path.suffix.lower() in forbidden_suffixes:
            raise SystemExit(f"forbidden runtime artifact generated: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
