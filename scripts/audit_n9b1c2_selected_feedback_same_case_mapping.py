#!/usr/bin/env python3
"""Audit N9B1C2 selected-feedback same-case mapping outputs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (  # noqa: E402
    L_DISABLED_CASE,
    M_CLEAN_REPEAT_CASE,
    MATRIX_STEMS,
    REPORT_NAMES,
    default_n9b1c2_runtime_root,
    run_n9b1c2_selected_feedback_same_case_mapping,
    validate_n9b1c2_result,
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
            result = run_n9b1c2_selected_feedback_same_case_mapping(ROOT, runtime_root=runtime_root, write_outputs=True)
        else:
            result = _load_written(runtime_root)
        _audit(runtime_root, result)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1c2"
            result = run_n9b1c2_selected_feedback_same_case_mapping(
                ROOT,
                runtime_root=runtime_root,
                write_outputs=True,
                run_wsl_dryrun=False,
            )
            _audit(runtime_root, result)
    print("audit_n9b1c2_selected_feedback_same_case_mapping passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    return {
        "selected_feedback_mapping_matrix": json.loads((runtime_root / "matrix" / "N9B1C2_SELECTED_FEEDBACK_MAPPING_MATRIX.json").read_text(encoding="utf-8")),
        "repaired_command_plan_matrix": json.loads((runtime_root / "matrix" / "N9B1C2_REPAIRED_COMMAND_PLAN_MATRIX.json").read_text(encoding="utf-8")),
        "wsl_dryrun_command_matrix": json.loads((runtime_root / "matrix" / "N9B1C2_WSL_DRYRUN_COMMAND_MATRIX.json").read_text(encoding="utf-8")),
    }


def _audit(runtime_root: Path, result: dict) -> None:
    validation = validate_n9b1c2_result(
        ROOT,
        runtime_root,
        result["selected_feedback_mapping_matrix"],
        result["repaired_command_plan_matrix"],
        result["wsl_dryrun_command_matrix"],
        runtime_written=True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1C2 validation failed: {validation['issues']}")
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
    rows = result["selected_feedback_mapping_matrix"]
    assert not [row for row in rows if row["routing_status"] == "not_selected_in_prior_plan"]
    assert not [
        row
        for row in rows
        if row["case_id"] not in {M_CLEAN_REPEAT_CASE, L_DISABLED_CASE}
        and row["mapping_status"] == "mapped"
        and row["acceptance_mode"] != "two_stage_same_case_feedback_generation_plan"
    ]
    assert not [row for row in rows if row["clean_n8j_path_used_for_degraded_case"]]
    assert not [row for row in rows if "future_solver_entry" in row["stage1_command"] or "future_solver_entry" in row["stage2_command"]]
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))
    assert not list(runtime_root.rglob("*.pdf"))


if __name__ == "__main__":
    raise SystemExit(main())
