#!/usr/bin/env python3
"""Dry-run-safe external final_v23/KF-GINS run wrapper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


RUN_ATTEMPT_FILENAME = "RUN_ATTEMPT.json"


def run_external(
    *,
    executable: str | Path,
    config: str | Path,
    output_dir: str | Path,
    dry_run: bool,
    allow_run: bool,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "phase": "N3C",
        "algorithm_role": "baseline",
        "executable": str(executable),
        "config": str(config),
        "output_dir": str(output),
        "dry_run": dry_run,
        "allow_run": allow_run,
        "trace_solver_input": False,
        "trace_used_for_tuning": False,
        "output_only_correction": False,
        "numerical_claim_without_oracle_pass": False,
        "evidence_status": "dry_run_not_executed",
    }
    if dry_run or not allow_run:
        return result
    if not Path(executable).is_file():
        result["evidence_status"] = "executable_missing"
        return result
    if not Path(config).is_file():
        result["evidence_status"] = "config_missing"
        return result

    completed = subprocess.run(
        [str(executable), str(config)],
        check=False,
        capture_output=True,
        text=True,
    )
    result["returncode"] = completed.returncode
    result["stdout_tail"] = completed.stdout[-4000:]
    result["stderr_tail"] = completed.stderr[-4000:]
    result["evidence_status"] = "executed_no_oracle_claim" if completed.returncode == 0 else "run_failed"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, help="External final_v23/KF-GINS executable.")
    parser.add_argument("--config", required=True, help="External final_v23/KF-GINS config.")
    parser.add_argument("--output-dir", required=True, help="Directory for RUN_ATTEMPT.json.")
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Default true. Pass --no-dry-run with --allow-run to execute.",
    )
    parser.add_argument("--allow-run", action="store_true", help="Allow a real external run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_external(
        executable=args.executable,
        config=args.config,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        allow_run=args.allow_run,
    )
    output_path = Path(args.output_dir) / RUN_ATTEMPT_FILENAME
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0 if result["evidence_status"] not in {"run_failed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
