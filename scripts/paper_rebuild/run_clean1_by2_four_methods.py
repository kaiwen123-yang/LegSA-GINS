#!/usr/bin/env python3
"""Run exactly the frozen CLEAN1 four-method set after all pre-run gates."""

from __future__ import annotations

import argparse
import json
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.formal_runner import FormalFourMethodRunner
from legsa_gins.paper_rebuild.manifest import write_json_atomic
from legsa_gins.paper_rebuild.paths import (
    assert_clean1_path_contract,
    clean1_stage_root,
    load_clean_paths,
)


def _completed_current_session_count(path: Path, session_id: str) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        successful_methods = {
            str(row.get("algorithm_id"))
            for row in csv.DictReader(handle)
            if row.get("session_id") == session_id
            and str(row.get("terminal_success")).casefold() == "true"
        }
    return len(successful_methods)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    paths = load_clean_paths(args.config)
    assert_clean1_path_contract(paths, REPO_ROOT)
    stage = clean1_stage_root(paths)
    runner = FormalFourMethodRunner(
        args.config,
        window_contract=stage / "02_PROTOCOL_FREEZE/WINDOW_CONTRACT.yaml",
        evaluator_contract=stage / "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.yaml",
        protocol_config=REPO_ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml",
        methods_config=REPO_ROOT / "configs/paper_rebuild/methods.yaml",
        attempt_ledger=stage / "06_RUN_MANIFESTS/FORMAL_RUN_ATTEMPT_LEDGER.csv",
    )
    try:
        manifests = runner.run()
    except Exception as exc:  # the exact fail-closed string is preserved in evidence
        completed_count = 0
        if runner.attempt_ledger.is_file():
            completed_count = _completed_current_session_count(
                runner.attempt_ledger, runner.attempt_session_id
            )
        payload = {
            "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
            "formal_run_count": completed_count,
            "method_count_required": 4,
            "metric_driven_rerun": False,
            "terminal_status": str(exc),
            "paper_performance_claim": False,
        }
        write_json_atomic(stage / "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({"formal_run_count": len(manifests), "terminal_status": "PASS"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
