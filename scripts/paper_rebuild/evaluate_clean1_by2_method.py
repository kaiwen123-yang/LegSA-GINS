#!/usr/bin/env python3
"""Evaluate one already frozen CLEAN1 method output in an isolated child process."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.evaluator import evaluate_formal_output
from legsa_gins.paper_rebuild.evidence import BY2_TRACE_RELATIVE_PATH
from legsa_gins.paper_rebuild.paths import (
    assert_clean1_path_contract,
    guard_path,
    load_clean_paths,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--solver-output", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--evaluator", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-output-sha256", required=True)
    args = parser.parse_args(argv)

    paths = load_clean_paths(args.config)
    assert_clean1_path_contract(paths, REPO_ROOT)
    stage = paths.clean_root / "06_CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION"
    solver = guard_path(
        args.solver_output,
        role="CLEAN1 current solver output",
        allowed_root=paths.runtime_root,
        must_exist=True,
        regular_file=True,
    )
    window = guard_path(
        args.window,
        role="CLEAN1 window contract",
        allowed_root=stage,
        must_exist=True,
        regular_file=True,
    )
    evaluator = guard_path(
        args.evaluator,
        role="CLEAN1 evaluator contract",
        allowed_root=stage,
        must_exist=True,
        regular_file=True,
    )
    output = guard_path(
        args.output_dir,
        role="CLEAN1 current evaluator output",
        allowed_root=stage / "07_EVALUATION",
    )
    result = evaluate_formal_output(
        solver,
        paths.raw_root / BY2_TRACE_RELATIVE_PATH,
        window,
        evaluator,
        output,
        expected_output_sha256=args.expected_output_sha256,
    )
    print(
        json.dumps(
            {
                "terminal_status": "PASS",
                "row_level_sha256": result["aggregate"]["row_level_sha256"],
                "output_sha256": result["aggregate"]["output_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
