#!/usr/bin/env python3
"""Claim-boundary helpers for PAPER10Q2 horizontal evidence reconciliation."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

REPRODUCTION_TYPES = (
    "EXACT_REPRODUCTION",
    "FAITHFUL_ALGORITHM_REPRODUCTION",
    "FAITHFUL_MODULE_REPRODUCTION",
    "PAPER_DERIVED_POLICY_BASELINE",
    "DIAGNOSTIC_ONLY",
    "BLOCKED_WITH_PROOF",
    "EXCLUDED_DEPRECATED",
)


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


def classify_reproduction_type(
    *,
    exact: bool = False,
    faithful_algorithm: bool = False,
    faithful_module: bool = False,
    paper_policy: bool = False,
    diagnostic: bool = False,
    blocked: bool = False,
    excluded: bool = False,
) -> str:
    if exact:
        return "EXACT_REPRODUCTION"
    if faithful_algorithm:
        return "FAITHFUL_ALGORITHM_REPRODUCTION"
    if faithful_module:
        return "FAITHFUL_MODULE_REPRODUCTION"
    if paper_policy:
        return "PAPER_DERIVED_POLICY_BASELINE"
    if diagnostic:
        return "DIAGNOSTIC_ONLY"
    if blocked:
        return "BLOCKED_WITH_PROOF"
    if excluded:
        return "EXCLUDED_DEPRECATED"
    return "DIAGNOSTIC_ONLY"


def flag_row(reproduction_type: str) -> dict[str, str]:
    return {
        "exact_reproduction": str(reproduction_type == "EXACT_REPRODUCTION").lower(),
        "faithful_algorithm": str(reproduction_type == "FAITHFUL_ALGORITHM_REPRODUCTION").lower(),
        "faithful_module": str(reproduction_type == "FAITHFUL_MODULE_REPRODUCTION").lower(),
        "paper_derived_policy": str(reproduction_type == "PAPER_DERIVED_POLICY_BASELINE").lower(),
        "diagnostic_only": str(reproduction_type == "DIAGNOSTIC_ONLY").lower(),
        "blocked_with_proof": str(reproduction_type == "BLOCKED_WITH_PROOF").lower(),
    }


def allowed_claim_rows() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "HC_ALLOWED_001",
            "claim_text": (
                "Representative horizontal comparison assets were reconciled by reproduction type, "
                "dataset coverage, and yaw/body-frame safety before paper use."
            ),
            "scope": "PAPER10Q2 evidence reconciliation only",
            "required_caveat": "No new solver/evaluator/provider/degradation run was performed in Q2.",
        },
        {
            "claim_id": "HC_ALLOWED_002",
            "claim_text": (
                "External algorithms from vehicle, marine, or generic GNSS/INS platforms are not rejected "
                "because of their original platform; BY2 can be used as a short-baseline legged stress condition "
                "when inputs are real and output semantics are closed."
            ),
            "scope": "horizontal-comparison design principle",
            "required_caveat": "Do not call a policy adapter a true external algorithm reproduction.",
        },
        {
            "claim_id": "HC_ALLOWED_003",
            "claim_text": (
                "Some existing dual-antenna evidence supports appendix-level native DD/LOS or module diagnostics, "
                "but current body-yaw superiority claims remain disallowed."
            ),
            "scope": "PAPER3/PAPER4G evidence",
            "required_caveat": "Native metrics are not same-evaluator body-yaw claims.",
        },
    ]


def conditional_claim_rows() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "HC_COND_001",
            "claim_text": "PAPER2A QA baselines may support a method-coverage table after row-level/proof re-export.",
            "condition": "PAPER2A row-level, runtime proof, method summary, render QA, and claim boundary are re-exported.",
            "paper_location": "appendix or bounded method-overview paragraph",
        },
        {
            "claim_id": "HC_COND_002",
            "claim_text": "A dual-antenna external-method comparison may enter main text after 3-5 true targeted methods close.",
            "condition": "Each targeted method independently runs on BY2 with real inputs and closed yaw/body/evaluator semantics.",
            "paper_location": "main text candidate only after targeted rerun gate",
        },
        {
            "claim_id": "HC_COND_003",
            "claim_text": "BY3 and XB horizontal stress may be discussed only as targeted stress evidence.",
            "condition": "Separate human-authorized stage and no ordinary yaw/general severe-GNSS claim.",
            "paper_location": "appendix or limitation/stress subsection",
        },
    ]


def appendix_claim_rows() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "HC_APP_001",
            "claim_text": "DD/LOS-backed dual-antenna module metrics can be listed as appendix evidence with yaw-frame caveats.",
            "scope": "PAPER3E/PAPER3F/PAPER3G/PAPER3H/PAPER4G native metrics",
            "reason": "Module/native evidence is useful, but not exact/full body-yaw reproduction.",
        },
        {
            "claim_id": "HC_APP_002",
            "claim_text": "Standard GNSS/INS QA wrappers can be listed as appendix quality-control baselines after re-export.",
            "scope": "PAPER2A/QA methods",
            "reason": "Common-backend QA wrappers are not full official external systems.",
        },
    ]


def diagnostic_claim_rows() -> list[dict[str, str]]:
    return [
        {
            "claim_id": "HC_DIAG_001",
            "claim_text": "PAPER1F dual-antenna adapters are diagnostic unless method-source mapping is repaired.",
            "scope": "PAPER1F",
            "reason": "Direct proof is secondary and method-family mapping is insufficient for true reproduction wording.",
        },
        {
            "claim_id": "HC_DIAG_002",
            "claim_text": "RTKLIB moving-base, GINav, blocked IEKF/EQKF, and frame-unsafe yaw assets are diagnostic only.",
            "scope": "blocked or frame-unsafe horizontal assets",
            "reason": "They do not close the required backend/body-yaw semantics.",
        },
    ]


def forbidden_claim_markdown() -> str:
    return "\n".join(
        [
            "# HORIZONTAL_FORBIDDEN_CLAIMS",
            "",
            "- Do not write that five external dual-antenna algorithms were exactly reproduced.",
            "- Do not write that twenty literature algorithms were exactly reproduced or completed.",
            "- Do not write universal superiority over all external methods.",
            "- Do not write that PAPER1F proves main-text superiority.",
            "- Do not write that PAPER2A proves performance superiority before re-export and classification support it.",
            "- Do not write BY3 ordinary yaw generalization.",
            "- Do not write XB high-precision severe-GNSS proof.",
            "- Do not write RTKLIB moving-base as faithful literature reproduction unless DD/LOS/ambiguity backends are closed.",
            "- Do not write method-inspired policy baselines as exact literature algorithms.",
            "- Do not write frame-unsafe yaw results as valid yaw claims.",
            "- Do not write old aggregate counts as completed matrices.",
            "- Do not write final paper claim ready.",
        ]
    )


def write_claim_boundary_outputs(out_dir: Path) -> None:
    write_csv(out_dir / "HORIZONTAL_ALLOWED_CLAIMS.csv", allowed_claim_rows())
    write_csv(out_dir / "HORIZONTAL_CONDITIONAL_CLAIMS.csv", conditional_claim_rows())
    write_csv(out_dir / "HORIZONTAL_APPENDIX_ONLY_CLAIMS.csv", appendix_claim_rows())
    write_csv(out_dir / "HORIZONTAL_DIAGNOSTIC_ONLY_CLAIMS.csv", diagnostic_claim_rows())
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "HORIZONTAL_FORBIDDEN_CLAIMS.md").write_text(forbidden_claim_markdown() + "\n", encoding="utf-8")
    freeze_lines = [
        "# HORIZONTAL_CLAIM_BOUNDARY_FREEZE",
        "",
        "PAPER10Q2 freezes horizontal comparison wording by evidence class.",
        "",
        "- Exact reproduction is currently not claimable from the reconciled assets.",
        "- Faithful algorithm reproduction requires independent BY2 execution with closed state/observation/backend semantics.",
        "- Faithful module reproduction may support appendix or bounded context, not full external-system claims.",
        "- Policy baselines and method-family adapters must remain diagnostic or appendix evidence.",
        "- BY3 remains poor-heading stress only; XB remains poor-GNSS stress only.",
    ]
    (out_dir / "HORIZONTAL_CLAIM_BOUNDARY_FREEZE.md").write_text("\n".join(freeze_lines) + "\n", encoding="utf-8")
