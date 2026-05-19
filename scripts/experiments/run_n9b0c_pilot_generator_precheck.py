#!/usr/bin/env python3
"""Run the N9B0C toy-only pilot generator implementation precheck."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_degradation_pilot_generators import (  # noqa: E402
    STAGE,
    discover_cleaned_matrix_root,
    run_pilot_generator_precheck,
)

AUDIT_ROOT_NAME = "by2\u6570\u636e\u96c6\u7ed8\u56fe\u5ba1\u8ba1"
DEFAULT_RUNTIME_ROOT = ROOT / AUDIT_ROOT_NAME / STAGE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", default=None)
    parser.add_argument("--runtime-root", "--output-dir", default=str(DEFAULT_RUNTIME_ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix_root = Path(args.matrix_root) if args.matrix_root else discover_cleaned_matrix_root(ROOT)
    runtime_root = Path(args.runtime_root)
    result = run_pilot_generator_precheck(matrix_root=matrix_root, runtime_root=runtime_root, write_outputs=True)
    decision = result["decision_report"]
    safety = result["safety_gate_report"]
    print("N9B0C pilot generator precheck complete")
    print("matrix_root:", matrix_root)
    print("runtime_root:", runtime_root)
    print("safety_status:", safety["status"])
    print("decision_status:", decision["status"])
    print("ready_for_N9B1_execution:", decision["ready_for_N9B1_execution"])
    print("ready_for_N9B_execution:", decision["ready_for_N9B_execution"])
    return 0 if safety["status"] == "pass" and decision["ready_for_N9B_execution"] is False else 1


if __name__ == "__main__":
    raise SystemExit(main())
