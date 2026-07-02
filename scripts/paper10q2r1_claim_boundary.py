#!/usr/bin/env python3
"""Claim-boundary helpers for PAPER10Q2R1."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def paper2a_allowed_claims() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "P2A_ALLOWED_001",
            "claim_text": "Seven QA/QC baselines were previously reported in PAPER2A and are re-exported only as bounded QA evidence if direct row proof is present.",
            "scope": "appendix or bounded QA context",
            "required_caveat": "Exact official external reproduction is not claimed.",
        },
        {
            "claim_id": "P2A_ALLOWED_002",
            "claim_text": "PAPER2A provides quality-control context for LegSA source-aware/QM protection claims.",
            "scope": "quality-management comparison context",
            "required_caveat": "It does not replace Q2R2 dual-antenna targeted rerun.",
        },
        {
            "claim_id": "P2A_ALLOWED_003",
            "claim_text": "Trace was evaluation-only and receiver IMU was not used as Go2 body IMU if supported by source proof.",
            "scope": "forbidden-input audit",
            "required_caveat": "Use supervisor-only wording if row-level proof is missing.",
        },
    ]


def paper2a_conditional_claims() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "P2A_COND_001",
            "claim_text": "PAPER2A can support a QA appendix table.",
            "condition": "Direct row-level/proof/render-QA files are found or re-exported.",
            "paper_location": "appendix",
        },
        {
            "claim_id": "P2A_COND_002",
            "claim_text": "PAPER2A BY2/BY3/XB coverage counts can be cited.",
            "condition": "Counts are directly supported by row/proof tables; otherwise use count-from-supervisor-only caveat.",
            "paper_location": "method coverage table",
        },
    ]


def paper2a_appendix_claims() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "P2A_APP_001",
            "claim_text": "QA01-QA07 may be listed as recognized QA/QC baselines with common-backend/policy-boundary caveats.",
            "reason": "They contextualize source-aware/QM but do not prove external-system superiority.",
        }
    ]


def paper2a_diagnostic_claims() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "P2A_DIAG_001",
            "claim_text": "Performance-superiority comparisons against PAPER2A QA wrappers are diagnostic unless a later reviewed table supports them.",
            "reason": "Q2/Q2R1 do not promote QA wrappers to exact external algorithms.",
        }
    ]


def paper2a_forbidden_claims_md() -> str:
    return "\n".join(
        [
            "# PAPER2A_FORBIDDEN_CLAIMS",
            "",
            "- Do not claim PAPER2A proves exact external reproduction.",
            "- Do not claim PAPER2A proves universal performance superiority.",
            "- Do not claim PAPER2A proves LegSA beats all QA methods.",
            "- Do not claim PAPER2A proves BY3 yaw generalization.",
            "- Do not claim PAPER2A proves XB high-precision severe-GNSS.",
            "- Do not claim PAPER2A methods are full official GNSS/INS algorithms unless proven.",
            "- Do not claim PAPER2A replaces Q2R2 dual antenna targeted rerun.",
            "- Do not claim PAPER2A is a dual-antenna method comparison.",
        ]
    )


def write_paper2a_claim_boundary(out_dir: Path) -> None:
    write_csv(out_dir / "PAPER2A_ALLOWED_CLAIMS.csv", paper2a_allowed_claims())
    write_csv(out_dir / "PAPER2A_CONDITIONAL_CLAIMS.csv", paper2a_conditional_claims())
    write_csv(out_dir / "PAPER2A_APPENDIX_ONLY_CLAIMS.csv", paper2a_appendix_claims())
    write_csv(out_dir / "PAPER2A_DIAGNOSTIC_ONLY_CLAIMS.csv", paper2a_diagnostic_claims())
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "PAPER2A_FORBIDDEN_CLAIMS.md").write_text(paper2a_forbidden_claims_md() + "\n", encoding="utf-8")
    (out_dir / "PAPER2A_CLAIM_BOUNDARY_FREEZE.md").write_text(
        "\n".join(
            [
                "# PAPER2A_CLAIM_BOUNDARY_FREEZE",
                "",
                "PAPER2A is bounded QA appendix evidence unless direct row-level/proof evidence supports stronger wording.",
                "",
                "- `exact_reproduction=false` for all seven QA methods.",
                "- QA methods are quality-control context, not full official external GNSS/INS algorithms.",
                "- PAPER2A does not replace dual-antenna targeted rerun.",
                "- Supervisor-only counts must be labeled as supervisor-only, not row-proven.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
