#!/usr/bin/env python3
"""Audit N9B1D1 solver interface mapping repair outputs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1d1_solver_interface_mapping_fix import (  # noqa: E402
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1d1_solver_interface_mapping_fix,
    validate_n9b1d1_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", default=None)
    parser.add_argument("--write-runtime", action="store_true")
    parser.add_argument("--skip-wsl-dryrun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runtime_root:
        runtime_root = Path(args.runtime_root)
        if args.write_runtime:
            result = run_n9b1d1_solver_interface_mapping_fix(
                ROOT,
                runtime_root=runtime_root,
                write_outputs=True,
                run_wsl_dryrun=not args.skip_wsl_dryrun,
            )
        else:
            result = _load_written(runtime_root)
        _audit(runtime_root, result)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1d1"
            result = run_n9b1d1_solver_interface_mapping_fix(
                ROOT,
                runtime_root=runtime_root,
                write_outputs=True,
                run_wsl_dryrun=False,
            )
            _audit(runtime_root, result)
    print("audit_n9b1d1_solver_interface_mapping_fix passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    return {
        "runner_interface_inventory": json.loads((runtime_root / "matrix" / "N9B1D1_RUNNER_INTERFACE_INVENTORY.json").read_text(encoding="utf-8")),
        "command_mapping_matrix_repaired": json.loads((runtime_root / "matrix" / "N9B1D1_COMMAND_MAPPING_MATRIX_REPAIRED.json").read_text(encoding="utf-8")),
        "wsl_dryrun_repaired_commands": json.loads((runtime_root / "matrix" / "N9B1D1_WSL_DRYRUN_REPAIRED_COMMANDS.json").read_text(encoding="utf-8")),
        "n9b1d_ready_execution_matrix": json.loads((runtime_root / "matrix" / "N9B1D1_N9B1D_READY_EXECUTION_MATRIX.json").read_text(encoding="utf-8")),
        "decision_report": json.loads((runtime_root / "reports" / "N9B1D1_DECISION_REPORT.json").read_text(encoding="utf-8")),
    }


def _audit(runtime_root: Path, result: dict) -> None:
    validation = validate_n9b1d1_result(
        ROOT,
        runtime_root,
        result["runner_interface_inventory"],
        result["command_mapping_matrix_repaired"],
        result["wsl_dryrun_repaired_commands"],
        result["n9b1d_ready_execution_matrix"],
        runtime_written=True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1D1 validation failed: {validation['issues']}")
    for name in REPORT_NAMES:
        payload = json.loads((runtime_root / "reports" / name).read_text(encoding="utf-8"))
        if payload.get("ready_for_N9B2_execution") is True:
            raise SystemExit(f"{name} incorrectly enables N9B2")
        if payload.get("solver_run") is True or payload.get("official_evaluator_run") is True:
            raise SystemExit(f"{name} records solver/evaluator execution")
    for stem in MATRIX_STEMS:
        if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
            raise SystemExit(f"missing matrix CSV {stem}")
        if not (runtime_root / "matrix" / f"{stem}.json").is_file():
            raise SystemExit(f"missing matrix JSON {stem}")
    for row in result["command_mapping_matrix_repaired"]:
        command = row.get("command", "")
        if row.get("entrypoint", "").endswith("build/cpp/legsa_gins") and " --config " in f" {command} " and row.get("run_allowed_in_N9B1D") is True:
            raise SystemExit("legsa_gins --config command remains executable")
        if row.get("mapping_status") != "mapped" and row.get("run_allowed_in_N9B1D") is True:
            raise SystemExit("blocked row is still executable")
    if list(runtime_root.rglob("NAV*")) or list(runtime_root.rglob("STD*")) or list(runtime_root.rglob("EVAL_NAV*")) or list(runtime_root.rglob("RUN_MANIFEST*")):
        raise SystemExit("N9B1D1 generated forbidden solver outputs")
    if list(runtime_root.rglob("*.png")) or list(runtime_root.rglob("*.pdf")):
        raise SystemExit("N9B1D1 generated forbidden figure artifacts")


if __name__ == "__main__":
    raise SystemExit(main())
