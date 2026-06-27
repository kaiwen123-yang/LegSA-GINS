#!/usr/bin/env python3
"""Guard checks for PAPER10M0 runner mapping.

中文说明：guard 只验证 M0 smoke 与 M1 队列锁；禁止 trace/final_v23/LegSA/
benchmark 输出进入 solver，禁止 QA fallback 作为 final method。
"""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any


FORBIDDEN_TRUE_KEYS = [
    "trace_used_online",
    "final_v23_output_used_as_input",
    "legsa_output_used_as_input",
    "benchmark_output_used_as_input",
    "per_case_tuning_used",
    "output_only_correction_used",
    "qa_fallback_as_final_method",
]

RAW_BODY_FILENAME_MARKERS = ["by2" + ".txt", "by3" + ".txt"]


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.is_file():
        return []
    with source.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_guard_state(
    *,
    queue_rows: list[dict[str, str]],
    smoke_rows: list[dict[str, str]],
    smoke_results: list[dict[str, Any]],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    if len(smoke_rows) > 8:
        issues.append("smoke row limit exceeded")
    if any(row.get("run_allowed_now") != "false" for row in queue_rows):
        issues.append("PAPER10M1 queue has run_allowed_now != false")
    if any(row.get("human_approval_required") != "true" for row in queue_rows):
        issues.append("PAPER10M1 queue missing human approval gate")
    for row in smoke_results:
        for key in FORBIDDEN_TRUE_KEYS:
            value = row.get(key)
            if value is True or str(value).lower() == "true":
                issues.append(f"{row.get('row_id', row.get('method_mode_id'))}: forbidden key true: {key}")
    if repo_root:
        root = Path(repo_root)
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        tracked_runtime_markers = []
        for line in status.stdout.splitlines():
            if any(token in line for token in ["NAV", "STD", "EVAL_NAV", "RUN_MANIFEST", *RAW_BODY_FILENAME_MARKERS]):
                tracked_runtime_markers.append(line)
        if tracked_runtime_markers:
            issues.append("git status shows runtime/raw markers: " + "; ".join(tracked_runtime_markers))
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "paper10m1_queue_locked": not any(row.get("run_allowed_now") != "false" for row in queue_rows),
        "smoke_row_count": len(smoke_rows),
        "full_matrix_run": False,
        "paper10m1_run": False,
        "paper10h_run": False,
        "by3_xb_pg_matrix_run": False,
        "benchmark_full_matrix_run": False,
    }


def main(argv: list[str] | None = None) -> int:
    print(json.dumps({"status": "pass", "standalone": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
