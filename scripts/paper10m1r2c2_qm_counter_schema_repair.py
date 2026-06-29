#!/usr/bin/env python3
"""Write PAPER10M1R2C2 QM counter schema repair reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.qm.qm_counter_schema import count_mapping_rows  # noqa: E402
from scripts.paper10m1r2c_full_algorithm_matrix import read_csv, write_csv  # noqa: E402


def run(args: argparse.Namespace) -> dict[str, Any]:
    stage_root = Path(args.stage_root)
    out = stage_root / "05_QM_COUNTER_REPAIR"
    out.mkdir(parents=True, exist_ok=True)
    mapping = count_mapping_rows()
    write_csv(out / "PAPER10M1R2C2_QM_COUNTER_FIELD_MAPPING.csv", mapping)
    sentinel_path = stage_root / "04_CLEAN_SENTINEL" / "PAPER10M1R2C2_CLEAN_SENTINEL_RESULT_TABLE.csv"
    transparency_rows: list[dict[str, Any]] = []
    if sentinel_path.is_file():
        for row in read_csv(sentinel_path):
            method = row.get("method_mode_id", "")
            qm_required = str(row.get("qm_trace_required", "false")).lower() == "true"
            transparency_rows.append(
                {
                    "method_mode_id": method,
                    "qm_trace_required": row.get("qm_trace_required", ""),
                    "qm_trace_file_exists": row.get("qm_trace_file_exists", ""),
                    "qm_trace_has_state_actions": row.get("qm_trace_has_state_actions", ""),
                    "qm_trace_not_required": row.get("qm_trace_not_required", ""),
                    "a1_yaw_update_count": row.get("a1_yaw_update_count", ""),
                    "a1_yaw_accepted_count": row.get("a1_yaw_accepted_count", ""),
                    "a1_yaw_downweighted_count": row.get("a1_yaw_downweighted_count", ""),
                    "a1_yaw_rejected_count": row.get("a1_yaw_rejected_count", ""),
                    "qm_state_normal_count": row.get("qm_state_normal_count", ""),
                    "qm_state_downweight_count": row.get("qm_state_downweight_count", ""),
                    "qm_state_reject_count": row.get("qm_state_reject_count", ""),
                    "qm_state_hold_count": row.get("qm_state_hold_count", ""),
                    "qm_state_recovery_count": row.get("qm_state_recovery_count", ""),
                    "qm_state_fallback_count": row.get("qm_state_fallback_count", ""),
                    "legacy_bad_a1_consumed_count_valid_for_claim": row.get(
                        "legacy_bad_a1_consumed_count_valid_for_claim", "false"
                    ),
                    "clean_qm_transparency_status": (
                        "QM_REQUIRED_TRACE_PRESENT"
                        if qm_required and str(row.get("qm_trace_file_exists", "")).lower() == "true"
                        else "QM_NOT_REQUIRED"
                        if not qm_required
                        else "BLOCKED_QM_TRACE_MISSING"
                    ),
                }
            )
    write_csv(out / "PAPER10M1R2C2_CLEAN_QM_TRANSPARENCY_AFTER_REPAIR.csv", transparency_rows)
    report = [
        "# PAPER10M1R2C2 QM Counter Schema Report",
        "",
        "`bad_a1_consumed_count` is deprecated for claims.",
        "",
        "Replacement fields split total A1 yaw attempts, accepted/downweighted/rejected updates, QM state counts, and trace-required/present semantics.",
        "",
        "Claim rule: legacy `bad_a1_consumed_count` must not be used as consumed bad-A1 evidence.",
    ]
    (out / "PAPER10M1R2C2_QM_COUNTER_SCHEMA_REPORT.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    return {"mapping_rows": len(mapping), "transparency_rows": len(transparency_rows)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    return parser.parse_args()


def main() -> int:
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
