#!/usr/bin/env python3
"""Build clearly labeled PAPER10M1R2C1 evaluator-only corrected metrics when allowed."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.yaw_metric_repair import rebuild_corrected_metrics  # noqa: E402


def _load_yaw_corrections(path: str | Path) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if not row.get("row_id"):
                continue
            if row.get("evaluator_only_candidate", "").lower() != "true":
                continue
            rows[row["row_id"]] = {
                "yaw_transform_applied": row.get("best_provider_reference_transform", ""),
                "yaw_rmse_deg": row.get("best_provider_reference_rmse_deg", ""),
            }
    return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row-table", required=True)
    parser.add_argument("--yaw-audit-table", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--evaluator-only", action="store_true")
    parser.add_argument("--blocked-reason", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rebuild_corrected_metrics(
        row_table=args.row_table,
        output_dir=args.output_dir,
        yaw_corrections=_load_yaw_corrections(args.yaw_audit_table),
        evaluator_only=args.evaluator_only,
        blocked_reason=args.blocked_reason,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
