#!/usr/bin/env python3
"""Audit N9B1A1 downsample cadence policy repair outputs and boundaries."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.by2_downsample_cadence_policy_repair import (  # noqa: E402
    MATRIX_STEMS,
    OLD_DOWNSAMPLE_CASE_ID,
    REPAIRED_DOWNSAMPLE_CASE_ID,
    REPAIRED_PILOT_CASE_IDS,
    REPORT_NAMES,
    default_n9b1a1_runtime_root,
    run_downsample_cadence_policy_repair,
    validate_downsample_cadence_policy_repair,
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
            result = run_downsample_cadence_policy_repair(ROOT, runtime_root=runtime_root, matrix_root=matrix_root, write_outputs=True)
        else:
            result = _load_written(runtime_root)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "n9b1a1_audit"
            result = run_downsample_cadence_policy_repair(ROOT, runtime_root=runtime_root, matrix_root=matrix_root, write_outputs=True)
            _audit(result, runtime_root)
            print("audit_n9b1a1_downsample_cadence_policy_repair passed")
            return 0
    _audit(result, runtime_root)
    print("audit_n9b1a1_downsample_cadence_policy_repair passed")
    return 0


def _load_written(runtime_root: Path) -> dict:
    return {
        "degraded_input_index_repaired": json.loads((runtime_root / "matrix" / "N9B1A1_DEGRADED_INPUT_INDEX_REPAIRED.json").read_text(encoding="utf-8")),
        "random_value_index": [],
        "solver_command_plan_index_repaired": json.loads((runtime_root / "matrix" / "N9B1A1_SOLVER_COMMAND_PLAN_INDEX_REPAIRED.json").read_text(encoding="utf-8")),
        "pilot_ready_matrix_repaired": json.loads((runtime_root / "matrix" / "N9B1A1_PILOT_READY_MATRIX_REPAIRED.json").read_text(encoding="utf-8")),
        "pilot_case_plan_repaired": json.loads((runtime_root / "matrix" / "N9B1A1_PILOT_CASE_PLAN_REPAIRED.json").read_text(encoding="utf-8")),
        "full_matrix_downsample_repair": json.loads((runtime_root / "matrix" / "N9B1A1_FULL_MATRIX_DOWNSAMPLE_REPAIR.json").read_text(encoding="utf-8")),
        "gnss_cadence_audit": json.loads((runtime_root / "matrix" / "N9B1A1_GNSS_CADENCE_AUDIT.json").read_text(encoding="utf-8")),
        "decision_report": json.loads((runtime_root / "reports" / "N9B1A1_DECISION_REPORT.json").read_text(encoding="utf-8")),
    }


def _audit(result: dict, runtime_root: Path) -> None:
    random_index = result.get("random_value_index")
    if random_index is None:
        random_index = []
    validation = validate_downsample_cadence_policy_repair(
        runtime_root,
        result["degraded_input_index_repaired"],
        random_index,
        result["solver_command_plan_index_repaired"],
        result["pilot_ready_matrix_repaired"],
        True,
    )
    if validation["status"] != "pass":
        raise SystemExit(f"N9B1A1 validation failed: {validation['issues']}")
    for name in REPORT_NAMES:
        payload = json.loads((runtime_root / "reports" / name).read_text(encoding="utf-8"))
        if payload.get("ready_for_solver_execution") is True:
            raise SystemExit(f"{name} incorrectly enables solver execution")
    for stem in MATRIX_STEMS:
        if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
            raise SystemExit(f"missing matrix CSV {stem}")
        if not (runtime_root / "matrix" / f"{stem}.json").is_file():
            raise SystemExit(f"missing matrix JSON {stem}")
    pilot_cases = [row["case_id"] for row in result["pilot_case_plan_repaired"]]
    if pilot_cases != REPAIRED_PILOT_CASE_IDS:
        raise SystemExit(f"unexpected repaired pilot order: {pilot_cases}")
    degraded_cases = {row["case_id"] for row in result["degraded_input_index_repaired"]}
    if OLD_DOWNSAMPLE_CASE_ID in degraded_cases or REPAIRED_DOWNSAMPLE_CASE_ID not in degraded_cases:
        raise SystemExit("downsample pilot replacement was not applied to degraded input index")
    cadence_sources = {row["source_id"]: row for row in result.get("gnss_cadence_audit", [])}
    for source_id in ["single7_clean_input", "dual15_clean_input", "gnss1_status_source", "final_v23_15col_source"]:
        if source_id not in cadence_sources:
            raise SystemExit(f"missing cadence audit source {source_id}")
    for row in cadence_sources.values():
        for key in [
            "path",
            "row_count",
            "time_start",
            "time_end",
            "duration",
            "median_dt",
            "p95_dt",
            "estimated_hz",
            "supports_5Hz_downsample",
            "supports_2Hz_downsample",
            "supports_1Hz_downsample",
            "supports_ratio_every2",
            "supports_ratio_every5",
            "source_role",
            "approved_for_current_runner",
        ]:
            if key not in row:
                raise SystemExit(f"cadence audit row missing {key}: {row.get('source_id')}")
    if any(row["approved_for_current_runner"] and row["supports_2Hz_downsample"] for row in cadence_sources.values()):
        raise SystemExit("current approved locked sources must not be treated as supporting 2Hz downsample")
    if any(row["case_id"] == REPAIRED_DOWNSAMPLE_CASE_ID for row in random_index):
        raise SystemExit("repaired downsample case must not create random values")
    if not any(row["case_id"] == OLD_DOWNSAMPLE_CASE_ID and row["repair_status"].startswith("blocked") for row in result["full_matrix_downsample_repair"]):
        raise SystemExit("old absolute 2Hz full-matrix case must remain blocked")
    decision = result["decision_report"]
    if decision["status"] != "N9B1A1_downsample_cadence_repair_complete":
        raise SystemExit(f"unexpected N9B1A1 decision status: {decision['status']}")
    if decision["ready_for_solver_execution"] is not False or decision["ready_for_N9B2_execution"] is not False:
        raise SystemExit("solver and N9B2 execution must remain disabled")


if __name__ == "__main__":
    raise SystemExit(main())
