#!/usr/bin/env python3
"""Audit N9B1C4 selected-feedback command field completion outputs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1c4_selected_feedback_command_field_completion import (  # noqa: E402
    MATRIX_STEMS,
    REPORT_NAMES,
    run_n9b1c4_selected_feedback_command_field_completion,
    validate_n9b1c4_result,
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
            result = run_n9b1c4_selected_feedback_command_field_completion(ROOT, runtime_root=runtime_root, write_outputs=True)
        else:
            result = _load_written(runtime_root)
        _audit(runtime_root, result)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1c4"
            result = run_n9b1c4_selected_feedback_command_field_completion(
                ROOT,
                runtime_root=runtime_root,
                write_outputs=True,
                run_wsl_dryrun_refresh=False,
            )
            _audit(runtime_root, result)
    print("audit_n9b1c4_selected_feedback_command_field_completion passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    return {
        "n9b1d_ready_command_matrix": json.loads((runtime_root / "matrix" / "N9B1C4_N9B1D_READY_COMMAND_MATRIX.json").read_text(encoding="utf-8")),
        "command_field_completion_diff": json.loads((runtime_root / "matrix" / "N9B1C4_COMMAND_FIELD_COMPLETION_DIFF.json").read_text(encoding="utf-8")),
        "wsl_dryrun_refresh": json.loads((runtime_root / "matrix" / "N9B1C4_WSL_DRYRUN_REFRESH.json").read_text(encoding="utf-8")),
        "dependency_graph_cleanup_report": json.loads((runtime_root / "reports" / "N9B1C4_DEPENDENCY_GRAPH_CLEANUP_REPORT.json").read_text(encoding="utf-8")),
    }


def _audit(runtime_root: Path, result: dict) -> None:
    validation = validate_n9b1c4_result(
        ROOT,
        runtime_root,
        result["n9b1d_ready_command_matrix"],
        result["command_field_completion_diff"],
        result["wsl_dryrun_refresh"],
        result["dependency_graph_cleanup_report"],
        runtime_written=True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1C4 validation failed: {validation['issues']}")
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
    selected = [
        row
        for row in result["n9b1d_ready_command_matrix"]
        if row.get("algorithm") == "selected_feedback_EKF" and row.get("run_allowed_in_N9B1D") is True
    ]
    assert len(selected) == 8
    assert not [row for row in selected if not row.get("entrypoint")]
    assert not [row for row in selected if not row.get("working_directory")]
    assert not [row for row in selected if not row.get("solver_command_json")]
    assert all(row.get("executed") is False for row in result["wsl_dryrun_refresh"])
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))
    assert not list(runtime_root.rglob("*.pdf"))


if __name__ == "__main__":
    raise SystemExit(main())
