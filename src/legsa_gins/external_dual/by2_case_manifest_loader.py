"""Case-manifest loader for the Q2R2R1 A1 120-case matrix."""

from __future__ import annotations

import csv
from pathlib import Path


def load_case_manifest(path: Path, *, limit: int = 120) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))[:limit]
    if len(rows) != limit:
        raise ValueError(f"expected {limit} case rows, got {len(rows)}")
    for row in rows:
        row.setdefault("trace_eval_only", "true")
        row.setdefault("final_v23_output_solver_input_allowed", "false")
        row.setdefault("legsa_output_solver_input_allowed", "false")
    return rows
