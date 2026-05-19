#!/usr/bin/env python3
"""Run the N9B0B degradation runner metadata-only dry-run precheck."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_degradation_runner_precheck import (
    discover_cleaned_matrix_root,
    run_dryrun_precheck,
)

AUDIT_ROOT_NAME = "by2\u6570\u636e\u96c6\u7ed8\u56fe\u5ba1\u8ba1"
DEFAULT_RUNTIME_ROOT = ROOT / AUDIT_ROOT_NAME / "N9B0B_DEGRADATION_RUNNER_IMPLEMENTATION_AND_DRYRUN_PRECHECK"
DEFAULT_NORMAL_PACKAGE_ROOT = ROOT / AUDIT_ROOT_NAME / "\u6b63\u5e38\u5de5\u51b5"
DEFAULT_R4E3_ROOT = ROOT / AUDIT_ROOT_NAME / "N9A_R4E3_OFFICIAL_EVALUATOR_PARITY_AND_METRIC_RECOMPUTE"
DEFAULT_R4J_ROOT = ROOT / AUDIT_ROOT_NAME / "N9A_R4J_GNSS1_STATUS_BASELINE_PROVENANCE_AND_CONTROLLED_REBUILD"
DEFAULT_R4P_ROOT = ROOT / AUDIT_ROOT_NAME / "N9A_R4P_RANDOMNESS_PROVENANCE_MANIFEST"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", default=None)
    parser.add_argument("--runtime-root", "--output-dir", default=str(DEFAULT_RUNTIME_ROOT))
    parser.add_argument("--normal-package-root", default=str(DEFAULT_NORMAL_PACKAGE_ROOT))
    parser.add_argument("--r4e3-root", default=str(DEFAULT_R4E3_ROOT))
    parser.add_argument("--r4j-root", default=str(DEFAULT_R4J_ROOT))
    parser.add_argument("--r4p-root", default=str(DEFAULT_R4P_ROOT))
    parser.add_argument("--data-paths-local", default=str(ROOT / "docs" / "codex_context" / "DATA_PATHS.local.md"))
    parser.add_argument("--official-evaluator-path", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix_root = Path(args.matrix_root) if args.matrix_root else discover_cleaned_matrix_root(ROOT)
    runtime_root = Path(args.runtime_root)
    context_paths = {
        "normal_package_root": Path(args.normal_package_root),
        "r4e3_root": Path(args.r4e3_root),
        "r4j_root": Path(args.r4j_root),
        "r4p_root": Path(args.r4p_root),
        "data_paths_local": Path(args.data_paths_local),
        "official_evaluator_path": Path(args.official_evaluator_path) if args.official_evaluator_path else None,
    }
    result = run_dryrun_precheck(
        matrix_root=matrix_root,
        runtime_root=runtime_root,
        write_outputs=True,
        context_paths=context_paths,
    )
    decision = result["decision_report"]
    validation = result["validation"]
    print("N9B0B degradation runner dry-run precheck complete")
    print("matrix_root:", matrix_root)
    print("runtime_root:", runtime_root)
    print("validation_status:", validation["status"])
    print("decision_status:", decision["status"])
    print("ready_for_N9B_execution:", decision["ready_for_N9B_execution"])
    return 0 if validation["status"] == "pass" and decision["ready_for_N9B_execution"] is False else 1


if __name__ == "__main__":
    raise SystemExit(main())
