#!/usr/bin/env python3
"""Audit N9B1C real solver entrypoint and config mapping outputs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_real_solver_entrypoint_config_mapping import (  # noqa: E402
    MATRIX_STEMS,
    REPORT_NAMES,
    default_n9b1c_runtime_root,
    run_real_solver_entrypoint_config_mapping,
    validate_n9b1c_result,
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
            result = run_real_solver_entrypoint_config_mapping(ROOT, runtime_root=runtime_root, matrix_root=matrix_root, write_outputs=True)
        else:
            result = _load_written(runtime_root)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1c_audit"
            result = run_real_solver_entrypoint_config_mapping(ROOT, runtime_root=runtime_root, matrix_root=matrix_root, write_outputs=True)
            _audit(result, runtime_root)
            print("audit_n9b1c_real_solver_entrypoint_config_mapping passed")
            return 0
    _audit(result, runtime_root)
    print("audit_n9b1c_real_solver_entrypoint_config_mapping passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    return {
        "command_mapping_matrix": json.loads((runtime_root / "matrix" / "N9B1C_COMMAND_MAPPING_MATRIX.json").read_text(encoding="utf-8")),
        "algorithm_ready_matrix": json.loads((runtime_root / "matrix" / "N9B1C_ALGORITHM_READY_MATRIX.json").read_text(encoding="utf-8")),
        "blocked_mapping_matrix": json.loads((runtime_root / "matrix" / "N9B1C_BLOCKED_MAPPING_MATRIX.json").read_text(encoding="utf-8")),
        "wsl_dryrun_command_matrix": json.loads((runtime_root / "matrix" / "N9B1C_WSL_DRYRUN_COMMAND_MATRIX.json").read_text(encoding="utf-8")),
        "decision_report": json.loads((runtime_root / "reports" / "N9B1C_DECISION_REPORT.json").read_text(encoding="utf-8")),
    }


def _audit(result: dict, runtime_root: Path) -> None:
    validation = validate_n9b1c_result(
        runtime_root,
        result["command_mapping_matrix"],
        result["algorithm_ready_matrix"],
        result["blocked_mapping_matrix"],
        result["wsl_dryrun_command_matrix"],
        runtime_written=True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1C validation failed: {validation['issues']}")
    for name in REPORT_NAMES:
        payload = json.loads((runtime_root / "reports" / name).read_text(encoding="utf-8"))
        if payload.get("ready_for_N9B2_execution") is True:
            raise SystemExit(f"{name} incorrectly enables N9B2 execution")
        if payload.get("solver_run") is True or payload.get("official_evaluator_run") is True:
            raise SystemExit(f"{name} incorrectly records solver/evaluator execution")
    for stem in MATRIX_STEMS:
        if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
            raise SystemExit(f"missing matrix CSV {stem}")
        if not (runtime_root / "matrix" / f"{stem}.json").is_file():
            raise SystemExit(f"missing matrix JSON {stem}")
    commands = [row.get("command", "") for row in result["command_mapping_matrix"]]
    if any("python -m legsa_gins.future_solver_entry" in command for command in commands):
        raise SystemExit("placeholder future_solver_entry command remains in N9B1C mapped commands")
    if any("N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING" in row.get("future_output_root", "") for row in result["command_mapping_matrix"] if row.get("mapping_status") == "mapped"):
        raise SystemExit("mapped output root points under N9B1C instead of future N9B1D")
    decision = result["decision_report"]
    if decision["ready_for_N9B2_execution"] is not False:
        raise SystemExit("N9B1C must never enable N9B2 execution")
    if list(runtime_root.rglob("NAV*")) or list(runtime_root.rglob("STD*")) or list(runtime_root.rglob("EVAL_NAV*")) or list(runtime_root.rglob("RUN_MANIFEST*")):
        raise SystemExit("N9B1C generated forbidden solver outputs")
    if list(runtime_root.rglob("*.png")) or list(runtime_root.rglob("*.pdf")):
        raise SystemExit("N9B1C generated forbidden figure artifacts")


if __name__ == "__main__":
    raise SystemExit(main())
