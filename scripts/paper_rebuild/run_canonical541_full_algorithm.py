#!/usr/bin/env python3
"""Prepare the exact plan, run C00, 32 formal smoke rows, then full 4x541."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from build_canonical541_manifest import load_base, load_local
from legsa_gins.paper_rebuild.canonical541.execution_plan import (
    execute_unique_selection, load_execution_plan, matrix_terminal_gate,
    prepare_execution_plan, storage_projection,
)
from legsa_gins.paper_rebuild.canonical541.runner import (
    TERMINAL_STATUSES, safe_initial_jobs, select_adaptive_jobs,
    validate_c00_structural_gate,
)
from legsa_gins.paper_rebuild.canonical541.authorization import authorize_operation, validate_attempt_root


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--local-config", required=True)
    result.add_argument("--executable", required=True)
    result.add_argument("--code-freeze-commit", required=True)
    result.add_argument("--hard-max-jobs", type=int, default=16)
    result.add_argument("--timeout-seconds", type=int, default=1800)
    result.add_argument("--resume", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    authorize_operation(REPO_ROOT, "solver")
    if not 8 <= args.hard_max_jobs <= 16:
        raise SystemExit("hard max jobs must be 8..16")
    local = Path(args.local_config).resolve(strict=True); paths = load_local(local)
    stage = validate_attempt_root(paths["runtime_root"])
    plan_path = stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json"
    if not plan_path.is_file():
        prepare_execution_plan(
            repo_root=REPO_ROOT, stage_root=stage, provider_root=paths["provider_root"],
            base_provider_root=paths["base_provider_root"], base=load_base(paths),
            executable=args.executable, code_freeze_commit=args.code_freeze_commit,
        )
    plan, unique, logical = load_execution_plan(
        stage_root=stage, repo_root=REPO_ROOT, executable=args.executable,
        code_freeze_commit=args.code_freeze_commit,
    )
    audits = stage / "16_AUDITS"; audits.mkdir(parents=True, exist_ok=True)
    projection_path = audits / "CANONICAL541_STORAGE_PROJECTION.json"
    if projection_path.is_file():
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        if projection.get("unique_run_count") != len(unique) or projection.get("projected_fits") is not True:
            raise SystemExit("stored storage projection no longer matches the exact unique plan")
    else:
        reference = paths["clean_root"] / "stages/CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME/06_FORMAL_RUNS"
        projection = storage_projection(
            unique_runs=unique, stage_root=stage, clean_ablation_runtime_root=reference,
        )
        projection_path.write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    c00_ids = {str(row["run_id"]) for row in unique if row["case_id"] == "C00_clean_normal"}
    initial_jobs = safe_initial_jobs(requested=8, hard_max=args.hard_max_jobs)
    unique, _ = execute_unique_selection(
        selected_run_ids=c00_ids, unique_rows=unique, logical_rows=logical,
        stage_root=stage, executable=args.executable, raw_root=paths["raw_root"],
        clean_root=paths["clean_root"], repo_root=REPO_ROOT,
        code_freeze_commit=args.code_freeze_commit, jobs=initial_jobs,
        timeout_seconds=args.timeout_seconds,
    )
    reference = paths["clean_root"] / "stages/CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME/06_FORMAL_RUNS"
    c00_gate = validate_c00_structural_gate(
        unique_runs=unique, logical_rows=logical, clean_ablation_runtime_root=reference,
        stage_root=stage,
        output_path=stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_C00_STRUCTURAL_GATE.json",
    )

    full_run_ids = {str(row["run_id"]) for row in logical if row["matrix"] == "full_algorithm"}
    smoke_path = audits / "CANONICAL541_PERFORMANCE_SMOKE.json"
    smoke_candidates = [
        row for row in sorted(unique, key=lambda item: int(item["run_order"]))
        if row["run_id"] in full_run_ids and row["case_id"] != "C00_clean_normal"
    ]
    if smoke_path.is_file():
        smoke_run_ids = json.loads(smoke_path.read_text(encoding="utf-8")).get("run_ids", [])
    else:
        smoke_run_ids = [str(row["run_id"]) for row in smoke_candidates[:32]]
        smoke_path.write_text(json.dumps({
            "formal_matrix_rows": True, "results_reused": True,
            "run_ids": smoke_run_ids, "selection_frozen_before_launch": True,
            "metric_read_count": 0, "trace_used_online": False, "passed": False,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if len(smoke_run_ids) != 32:
        raise SystemExit("unable to identify exactly 32 reusable formal smoke rows")
    unique, _ = execute_unique_selection(
        selected_run_ids=smoke_run_ids, unique_rows=unique, logical_rows=logical,
        stage_root=stage, executable=args.executable, raw_root=paths["raw_root"],
        clean_root=paths["clean_root"], repo_root=REPO_ROOT,
        code_freeze_commit=args.code_freeze_commit, jobs=initial_jobs,
        timeout_seconds=args.timeout_seconds,
    )
    by_run = {str(row["run_id"]): row for row in unique}
    smoke_proofs = [
        json.loads((Path(str(by_run[run_id]["output_root"])) / "CANONICAL541_EXECUTION_PROOF.json").read_text(encoding="utf-8"))
        for run_id in smoke_run_ids
    ]
    adaptive = select_adaptive_jobs(smoke_proofs, hard_max=args.hard_max_jobs)
    smoke_report = {
        "formal_matrix_rows": True, "results_reused": True, "run_ids": smoke_run_ids,
        "adaptive_parallelism": adaptive, "metric_read_count": 0,
        "trace_used_online": False, "passed": True,
    }
    smoke_path.write_text(
        json.dumps(smoke_report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    remaining = {
        str(row["run_id"]) for row in unique
        if row["run_id"] in full_run_ids and row.get("terminal_status") not in TERMINAL_STATUSES
    }
    unique, _ = execute_unique_selection(
        selected_run_ids=remaining, unique_rows=unique, logical_rows=logical,
        stage_root=stage, executable=args.executable, raw_root=paths["raw_root"],
        clean_root=paths["clean_root"], repo_root=REPO_ROOT,
        code_freeze_commit=args.code_freeze_commit, jobs=int(adaptive["selected_jobs"]),
        timeout_seconds=args.timeout_seconds,
    )
    full_gate = matrix_terminal_gate(
        matrix="full_algorithm", unique_rows=unique, logical_rows=logical,
        output_path=audits / "CANONICAL541_FULL_ALGORITHM_TERMINAL_GATE.json",
    )
    print(json.dumps({
        "plan": plan, "storage_projection": projection, "c00_gate": c00_gate,
        "smoke": smoke_report, "full_gate": full_gate,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
