#!/usr/bin/env python3
"""Audit N9B1C3 execution matrix hygiene and dependency-order outputs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1c3_execution_matrix_hygiene_dependency_order import (  # noqa: E402
    MATRIX_STEMS,
    REPORT_NAMES,
    default_n9b1c3_runtime_root,
    run_n9b1c3_execution_matrix_hygiene_dependency_order,
    validate_n9b1c3_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", default=None)
    parser.add_argument("--write-runtime", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runtime_root:
        runtime_root = Path(args.runtime_root)
        if args.write_runtime:
            result = run_n9b1c3_execution_matrix_hygiene_dependency_order(ROOT, runtime_root=runtime_root, write_outputs=True)
        else:
            result = _load_written(runtime_root)
        _audit(runtime_root, result)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1c3"
            result = run_n9b1c3_execution_matrix_hygiene_dependency_order(
                ROOT,
                runtime_root=runtime_root,
                write_outputs=True,
                run_wsl_path_preflight=False,
                run_wsl_dryrun_refresh=False,
            )
            _audit(runtime_root, result)
    print("audit_n9b1c3_execution_matrix_hygiene_dependency_order passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    return {
        "n9b1d_ready_command_matrix": json.loads((runtime_root / "matrix" / "N9B1C3_N9B1D_READY_COMMAND_MATRIX.json").read_text(encoding="utf-8")),
        "stale_field_diff": json.loads((runtime_root / "matrix" / "N9B1C3_STALE_FIELD_DIFF.json").read_text(encoding="utf-8")),
        "case_dependency_graph": json.loads((runtime_root / "matrix" / "N9B1C3_CASE_DEPENDENCY_GRAPH.json").read_text(encoding="utf-8")),
        "wsl_path_preflight": json.loads((runtime_root / "matrix" / "N9B1C3_WSL_PATH_PREFLIGHT.json").read_text(encoding="utf-8")),
        "wsl_dryrun_refresh": json.loads((runtime_root / "matrix" / "N9B1C3_WSL_DRYRUN_REFRESH.json").read_text(encoding="utf-8")),
    }


def _audit(runtime_root: Path, result: dict) -> None:
    validation = validate_n9b1c3_result(
        ROOT,
        runtime_root,
        result["n9b1d_ready_command_matrix"],
        result["stale_field_diff"],
        result["case_dependency_graph"],
        result["wsl_path_preflight"],
        result["wsl_dryrun_refresh"],
        runtime_written=True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1C3 validation failed: {validation['issues']}")
    for report in REPORT_NAMES:
        payload = json.loads((runtime_root / "reports" / report).read_text(encoding="utf-8"))
        if payload.get("ready_for_N9B2_execution") is True:
            raise SystemExit(f"{report} incorrectly enables N9B2")
        if payload.get("solver_run") is True or payload.get("official_evaluator_run") is True:
            raise SystemExit(f"{report} incorrectly records solver/evaluator execution")
    for stem in MATRIX_STEMS:
        if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
            raise SystemExit(f"missing matrix CSV {stem}")
        if not (runtime_root / "matrix" / f"{stem}.json").is_file():
            raise SystemExit(f"missing matrix JSON {stem}")
    rows = result["n9b1d_ready_command_matrix"]
    assert not [row for row in rows if row.get("n9b1d_executable") is True and row.get("block_reason")]
    assert not [row for row in rows if row.get("n9b1d_executable") is True and row.get("blocked_reason")]
    assert not [row for row in rows if row.get("n9b1d_executable") is True and "future_solver_entry" in row.get("command", "")]
    assert not [row for row in rows if row.get("algorithm") == "selected_feedback_EKF" and row.get("mapping_status") == "mapped" and row.get("selected_feedback_acceptance") == "blocked"]
    assert all(row.get("executed") is False for row in result["wsl_dryrun_refresh"])
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))
    assert not list(runtime_root.rglob("*.pdf"))


if __name__ == "__main__":
    raise SystemExit(main())
