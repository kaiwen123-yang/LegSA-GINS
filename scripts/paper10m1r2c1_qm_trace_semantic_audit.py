#!/usr/bin/env python3
"""Generate PAPER10M1R2C1 QM trace semantic audit tables."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.qm_trace_semantic_audit import (  # noqa: E402
    audit_qm_semantics,
    qm_gate_status,
    summarize_clean_qm,
    write_csv_rows,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    stage_root = Path(args.stage_root)
    qm_dir = stage_root / "03_QM_AUDIT"
    qm_dir.mkdir(parents=True, exist_ok=True)
    rows = audit_qm_semantics(args.row_table, args.m1r2c_runtime_root)
    clean_summary = summarize_clean_qm(rows)
    gate = qm_gate_status(clean_summary)
    write_csv_rows(qm_dir / "PAPER10M1R2C1_QM_TRACE_SEMANTIC_AUDIT_TABLE.csv", rows)
    _write_json(qm_dir / "PAPER10M1R2C1_QM_GATE_SUMMARY.json", {**clean_summary, **gate})

    clean_rows = [row for row in rows if row.get("case_id") == "BY2_CLEAN_CANONICAL"]
    bad_rows = [row for row in clean_rows if int(row.get("bad_a1_consumed_count_original", 0) or 0) > 0]
    (qm_dir / "PAPER10M1R2C1_BAD_A1_CONSUMED_SEMANTIC_REPORT.md").write_text(
        "\n".join(
            [
                "# PAPER10M1R2C1 Bad A1 Counter Semantic Report",
                "",
                "`bad_a1_consumed_count` is not claim-valid in M1R2C.",
                "For rows where it is nonzero, it maps to runtime `yaw_REJECT`, not to proven bad A1 actually consumed.",
                f"Clean rows with nonzero original counter: {len(bad_rows)}.",
                "",
                "Required fix: rename the collector field or split it into accepted/downweighted/rejected A1 diagnostic counters.",
                "No paper claim may use `bad_a1_consumed_count` until the split fields are implemented and reviewed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (qm_dir / "PAPER10M1R2C1_QM_CLEAN_TRANSPARENCY_AUDIT.md").write_text(
        "\n".join(
            [
                "# PAPER10M1R2C1 QM Clean Transparency Audit",
                "",
                f"Clean rows audited: {clean_summary['clean_rows']}.",
                f"Full-QM downweight count: {clean_summary['full_qm_downweight_count']}.",
                f"Full-QM recovery count: {clean_summary['full_qm_recovery_count']}.",
                f"Full-QM reject count: {clean_summary['full_qm_reject_count']}.",
                f"Transparency pass: {str(clean_summary['clean_qm_transparency_pass']).lower()}.",
                "",
                "Clean full-QM behavior is not transparent when downweight/recovery/reject counts are nonzero.",
                "This blocks claim use and blocks M1R2D if paired with unresolved clean yaw semantics.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (qm_dir / "PAPER10M1R2C1_QM_FIELD_DEFINITION_FIX_RECOMMENDATION.md").write_text(
        "\n".join(
            [
                "# PAPER10M1R2C1 QM Field Definition Fix Recommendation",
                "",
                "Recommended collector/schema changes:",
                "",
                "- Split `qm_trace_exists_or_not_required` into `qm_trace_required`, `qm_trace_file_exists`, `qm_trace_not_required`, and `qm_trace_has_state_actions`.",
                "- Split `source_trace_exists_or_not_required` into `source_trace_required`, `source_trace_file_exists`, and `source_trace_not_required`.",
                "- Replace or rename `bad_a1_consumed_count`; current M1R2C semantics match `yaw_REJECT`.",
                "- Add `a1_diagnostic_count`, `bad_a1_accepted_count`, `bad_a1_rejected_count`, `bad_a1_downweighted_count`, and `qm_action_count_by_source`.",
                "- Keep all QM/source counters blocked from paper claims until semantic review passes.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {**clean_summary, **gate}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--m1r2c-runtime-root", required=True)
    parser.add_argument("--row-table", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    run(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
