#!/usr/bin/env python3
"""Audit N9B1C1 routing-command consistency repair outputs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1c1_routing_command_consistency import (  # noqa: E402
    MATRIX_STEMS,
    REPORT_NAMES,
    default_n9b1c1_runtime_root,
    run_n9b1c1_routing_command_consistency_fix,
    validate_n9b1c1_result,
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
            result = run_n9b1c1_routing_command_consistency_fix(ROOT, runtime_root=runtime_root, write_outputs=True)
        else:
            result = _load_written(runtime_root)
        _audit(runtime_root, result)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1c1"
            result = run_n9b1c1_routing_command_consistency_fix(ROOT, runtime_root=runtime_root, write_outputs=True, run_wsl_dryrun=False)
            _audit(runtime_root, result)
    print("audit_n9b1c1_routing_command_consistency_fix passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    return {
        "command_mapping_matrix_repaired": json.loads((runtime_root / "matrix" / "N9B1C1_COMMAND_MAPPING_MATRIX_REPAIRED.json").read_text(encoding="utf-8")),
        "wsl_dryrun_command_matrix": json.loads((runtime_root / "matrix" / "N9B1C1_WSL_DRYRUN_COMMAND_MATRIX.json").read_text(encoding="utf-8")),
    }


def _audit(runtime_root: Path, result: dict) -> None:
    validation = validate_n9b1c1_result(
        runtime_root,
        result["command_mapping_matrix_repaired"],
        result["wsl_dryrun_command_matrix"],
        runtime_written=True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1C1 validation failed: {validation['issues']}")
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
    rows = result["command_mapping_matrix_repaired"]
    assert not [row for row in rows if row.get("routing_status") == "not_selected_in_prior_plan" and (row.get("mapping_status") == "mapped" or row.get("run_allowed_in_N9B1D") or row.get("command"))]
    assert not [row for row in rows if row.get("mapping_status") == "fixed_reference" and (row.get("command") or row.get("run_allowed_in_N9B1D"))]
    assert not [row for row in rows if row.get("command") and "future_solver_entry" in row.get("command", "")]
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))
    assert not list(runtime_root.rglob("*.pdf"))


if __name__ == "__main__":
    raise SystemExit(main())
