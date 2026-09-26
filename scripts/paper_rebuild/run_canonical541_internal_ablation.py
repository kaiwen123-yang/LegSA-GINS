#!/usr/bin/env python3
"""Resume the plan, run the seven remaining ablations, resolve 7,033 and seal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from build_canonical541_manifest import load_local
from legsa_gins.paper_rebuild.canonical541.execution_plan import (
    execute_unique_selection, load_execution_plan, matrix_terminal_gate,
    rebuild_attempt_registry,
)
from legsa_gins.paper_rebuild.canonical541.runner import (
    TERMINAL_STATUSES, seal_unique_outputs, validate_output_seal,
)
from legsa_gins.paper_rebuild.canonical541.raw_audit import ensure_raw_checkpoint
from legsa_gins.paper_rebuild.canonical541.authorization import authorize_operation, validate_attempt_root


EXPECTED_RAW_LOCK_SHA256 = "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--local-config", required=True)
    result.add_argument("--executable", required=True)
    result.add_argument("--code-freeze-commit", required=True)
    result.add_argument("--jobs", type=int)
    result.add_argument("--timeout-seconds", type=int, default=1800)
    result.add_argument("--resume", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    authorize_operation(REPO_ROOT, "internal_ablation")
    paths = load_local(Path(args.local_config).resolve(strict=True))
    stage = validate_attempt_root(paths["runtime_root"]); audits = stage / "16_AUDITS"
    full_gate_path = audits / "CANONICAL541_FULL_ALGORITHM_TERMINAL_GATE.json"
    full_gate = json.loads(full_gate_path.read_text(encoding="utf-8"))
    if full_gate.get("passed") is not True or full_gate.get("logical_row_count") != 2164:
        raise SystemExit("full algorithm matrix gate must pass before internal ablation")
    plan, unique, logical = load_execution_plan(
        stage_root=stage, repo_root=REPO_ROOT, executable=args.executable,
        code_freeze_commit=args.code_freeze_commit,
    )
    if args.jobs is None:
        smoke = json.loads((audits / "CANONICAL541_PERFORMANCE_SMOKE.json").read_text(encoding="utf-8"))
        jobs = int(smoke["adaptive_parallelism"]["selected_jobs"])
    else:
        jobs = args.jobs
    if not 1 <= jobs <= 16:
        raise SystemExit("jobs must be 1..16")
    internal_run_ids = {str(row["run_id"]) for row in logical if row["matrix"] == "internal_ablation"}
    remaining = {
        str(row["run_id"]) for row in unique
        if row["run_id"] in internal_run_ids and row.get("terminal_status") not in TERMINAL_STATUSES
    }
    unique, _ = execute_unique_selection(
        selected_run_ids=remaining, unique_rows=unique, logical_rows=logical,
        stage_root=stage, executable=args.executable, raw_root=paths["raw_root"],
        clean_root=paths["clean_root"], repo_root=REPO_ROOT,
        code_freeze_commit=args.code_freeze_commit, jobs=jobs,
        timeout_seconds=args.timeout_seconds,
    )
    ablation_gate = matrix_terminal_gate(
        matrix="internal_ablation", unique_rows=unique, logical_rows=logical,
        output_path=audits / "CANONICAL541_INTERNAL_ABLATION_TERMINAL_GATE.json",
    )
    seal_root = stage / "11_OUTPUT_SEAL"
    seal_manifest = seal_root / "OUTPUT_HASH_MANIFEST.csv"
    seal_journal = seal_root / "OUTPUT_SEAL_JOURNAL.json"
    if seal_manifest.is_file() and seal_journal.is_file():
        seal = validate_output_seal(seal_root, raw_root=paths["raw_root"])
    elif seal_manifest.exists() or seal_journal.exists():
        raise SystemExit("partial output seal exists; refusing reconstruction over it")
    else:
        attempts = rebuild_attempt_registry(stage_root=stage)
        seal = seal_unique_outputs(
            unique, logical, seal_root, raw_root=paths["raw_root"], attempt_rows=attempts,
        )
        validate_output_seal(seal_root, raw_root=paths["raw_root"])
    post_run_raw = ensure_raw_checkpoint(
        raw_root=paths["raw_root"],
        hash_lock_path=paths["clean_root"] / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv",
        expected_lock_sha256=EXPECTED_RAW_LOCK_SHA256,
        expected_full_lock_rows=9980,
        output_root=audits,
        phase="POST_RUN",
    )
    report = {
        "plan_unique_run_count": plan["unique_run_count"],
        "full_algorithm_logical_rows": 2164, "internal_ablation_logical_rows": 4869,
        "all_logical_rows": 7033, "full_gate": full_gate,
        "ablation_gate": ablation_gate, "output_seal": seal,
        "post_run_raw_checkpoint": post_run_raw,
        "trace_used_online": False, "passed": True,
    }
    (audits / "CANONICAL541_ALL_LOGICAL_TERMINAL_GATE.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
