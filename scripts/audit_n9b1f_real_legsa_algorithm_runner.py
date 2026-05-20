#!/usr/bin/env python3
"""Audit N9B1F real LegSA algorithm runner outputs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import (  # noqa: E402
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1f_real_legsa_algorithm_runner,
    validate_n9b1f_result,
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
            result = run_n9b1f_real_legsa_algorithm_runner(ROOT, runtime_root=runtime_root, write_outputs=True)
        else:
            result = _load_written(runtime_root)
        _audit(runtime_root, result)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1f"
            result = run_n9b1f_real_legsa_algorithm_runner(ROOT, runtime_root=runtime_root, write_outputs=True)
            _audit(runtime_root, result)
    print("audit_n9b1f_real_legsa_algorithm_runner passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    return {
        "algorithm_implementation_inventory": json.loads((runtime_root / "matrix" / "N9B1F_ALGORITHM_IMPLEMENTATION_INVENTORY.json").read_text(encoding="utf-8")),
        "normal_parity_metrics": json.loads((runtime_root / "matrix" / "N9B1F_NORMAL_PARITY_METRICS.json").read_text(encoding="utf-8")),
        "n9b1d_ready_execution_matrix": json.loads((runtime_root / "matrix" / "N9B1F_N9B1D_READY_EXECUTION_MATRIX.json").read_text(encoding="utf-8")),
        "wsl_dryrun_ready_commands": json.loads((runtime_root / "matrix" / "N9B1F_WSL_DRYRUN_READY_COMMANDS.json").read_text(encoding="utf-8")),
        "decision_report": json.loads((runtime_root / "reports" / "N9B1F_DECISION_REPORT.json").read_text(encoding="utf-8")),
    }


def _audit(runtime_root: Path, result: dict) -> None:
    validation = validate_n9b1f_result(
        ROOT,
        runtime_root,
        result["algorithm_implementation_inventory"],
        result["normal_parity_metrics"],
        result["n9b1d_ready_execution_matrix"],
        result["wsl_dryrun_ready_commands"],
        runtime_written=True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1F validation failed: {validation['issues']}")
    for name in REPORT_NAMES:
        payload = json.loads((runtime_root / "reports" / name).read_text(encoding="utf-8"))
        if payload.get("ready_for_N9B2_execution") is True:
            raise SystemExit(f"{name} incorrectly enables N9B2")
    for stem in MATRIX_STEMS:
        if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
            raise SystemExit(f"missing matrix CSV {stem}")
        if not (runtime_root / "matrix" / f"{stem}.json").is_file():
            raise SystemExit(f"missing matrix JSON {stem}")
    for row in result["normal_parity_metrics"]:
        command = " ".join(row.get("solver_command", []) or [])
        if row.get("parity_passed") is True and "legsa_v23_port_core_demo" not in command:
            raise SystemExit("parity-passed row lacks port-core command")
        if "--run-filter-csv" in command or "build/cpp/legsa_gins" in command:
            raise SystemExit("diagnostic legsa_gins command used")
    if list(runtime_root.rglob("*.png")) or list(runtime_root.rglob("*.pdf")):
        raise SystemExit("N9B1F generated figures")
    if result["decision_report"].get("ready_for_N9B2_execution") is not False:
        raise SystemExit("N9B1F decision enables N9B2")


if __name__ == "__main__":
    raise SystemExit(main())
