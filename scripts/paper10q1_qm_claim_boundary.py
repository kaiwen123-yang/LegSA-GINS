#!/usr/bin/env python3
"""Claim-boundary helpers for PAPER10Q1 QM evidence review."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable


FORBIDDEN_CLAIM_KEYS = [
    "qm_universal_metric_improvement",
    "qm_significantly_improves_normal_accuracy",
    "full_qm_dominates_no_qm_all_cases",
    "legacy_bad_a1_consumed_count_claim",
    "by3_yaw_generalization",
    "xb_high_precision_severe_gnss_proof",
    "final_paper_claim_ready",
    "go2_truth",
    "trace_online_or_solver_input",
    "output_only_correction",
    "per_case_tuning",
    "old_m1r2c_yaw_invalid_result",
]


def claim_rows() -> dict[str, list[dict[str, str]]]:
    allowed = [
        {
            "claim_id": "Q1_A01",
            "claim_en": "QM/source-aware provides bounded protection under degraded measurement conditions.",
            "claim_cn": "QM/source-aware可写为在退化观测条件下提供有边界的保护机制。",
            "evidence_source": "M1R2C_R1/M1R2D_R1 QM and source-aware traces",
            "boundary": "Use family-specific wording; do not claim universal metric improvement.",
        },
        {
            "claim_id": "Q1_A02",
            "claim_en": "QM provides interpretable state/action/recovery traces.",
            "claim_cn": "QM提供可解释的状态、动作和恢复轨迹。",
            "evidence_source": "QM_STATE_ACTION_TRACE summaries and selected trace files",
            "boundary": "Mechanism evidence; not a final paper-ready superiority claim.",
        },
        {
            "claim_id": "Q1_A03",
            "claim_en": "Source-aware weighting has stable bounded contribution in many BY2 cases.",
            "claim_cn": "来源感知权重在许多BY2工况中具有稳定但有边界的贡献。",
            "evidence_source": "M1R2D_R1 no_source_aware ablation",
            "boundary": "Deltas are small and must be reported with tradeoffs.",
        },
    ]
    conditional = [
        {
            "claim_id": "Q1_C01",
            "claim_en": "Normal-condition QM transparency is acceptable only with reported costs.",
            "claim_cn": "正常工况QM透明性只能在报告精度代价后有条件成立。",
            "condition": "Clean-case deltas and action counts are reported.",
            "forbidden_upgrade": "Do not claim QM improves normal-condition accuracy.",
        },
        {
            "claim_id": "Q1_C02",
            "claim_en": "QM can be positioned as a protective and interpretable mechanism.",
            "claim_cn": "QM可定位为保护性和可解释性机制。",
            "condition": "State that RMSE improvements are not universal and no-QM can be better.",
            "forbidden_upgrade": "Do not write full-QM dominates no-QM.",
        },
    ]
    appendix = [
        {
            "claim_id": "Q1_P01",
            "claim_en": "D23-D29, D30-D41, D42-D50, and D58-D60 QM action heatmaps support appendix evidence.",
            "claim_cn": "D23-D29、D30-D41、D42-D50和D58-D60的QM动作热图可作为附录证据。",
            "paper_location": "appendix",
            "boundary": "Detailed support; not standalone main claim.",
        },
        {
            "claim_id": "Q1_P02",
            "claim_en": "No-QM better cases should be disclosed as a caveat panel.",
            "claim_cn": "no-QM更优case应作为权衡附录或审查图披露。",
            "paper_location": "appendix",
            "boundary": "Prevents overstating QM.",
        },
    ]
    diagnostic = [
        {
            "claim_id": "Q1_D01",
            "claim_en": "Legacy bad-A1 consumed counters are deprecated diagnostics only.",
            "claim_cn": "legacy bad-A1 consumed计数仅为废弃诊断字段。",
            "diagnostic_reason": "Not valid as a claim field.",
        },
        {
            "claim_id": "Q1_D02",
            "claim_en": "Cases where QM hurts or is neutral are diagnostic caveats.",
            "claim_cn": "QM变差或中性的case属于诊断性边界证据。",
            "diagnostic_reason": "Needed for claim boundary.",
        },
    ]
    return {
        "allowed": allowed,
        "conditional": conditional,
        "appendix": appendix,
        "diagnostic": diagnostic,
    }


def forbidden_claim_markdown() -> str:
    wording = {
        "qm_universal_metric_improvement": "Do not claim QM universally improves all metrics.",
        "qm_significantly_improves_normal_accuracy": "Do not claim QM significantly improves normal-condition accuracy.",
        "full_qm_dominates_no_qm_all_cases": "Do not claim full-QM dominates no-QM in all cases.",
        "legacy_bad_a1_consumed_count_claim": "Do not use legacy bad-A1 consumed counters as claim evidence.",
        "by3_yaw_generalization": "Do not claim BY3 yaw generalization.",
        "xb_high_precision_severe_gnss_proof": "Do not claim severe-GNSS high-precision proof for XB/PG.",
        "final_paper_claim_ready": "Do not claim final paper readiness.",
        "go2_truth": "Do not treat Go2 position, velocity, contact, or yaw as truth.",
        "trace_online_or_solver_input": "Do not use or imply trace online / trace solver input.",
        "output_only_correction": "Do not perform or claim output-only correction.",
        "per_case_tuning": "Do not tune per case.",
        "old_m1r2c_yaw_invalid_result": "Do not use old yaw-invalid M1R2C metrics.",
    }
    lines = [
        "# PAPER10Q1 Forbidden QM Claims",
        "",
        "These claim families are forbidden for Q1 and for any manuscript text derived from Q1.",
        "",
    ]
    for key in FORBIDDEN_CLAIM_KEYS:
        lines.append(f"- `{key}`: {wording[key]}")
    lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_claim_boundary_outputs(output_dir: Path) -> None:
    rows = claim_rows()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "QM_ALLOWED_CLAIMS.csv", rows["allowed"])
    write_csv(output_dir / "QM_CONDITIONAL_CLAIMS.csv", rows["conditional"])
    write_csv(output_dir / "QM_APPENDIX_ONLY_CLAIMS.csv", rows["appendix"])
    write_csv(output_dir / "QM_DIAGNOSTIC_ONLY_CLAIMS.csv", rows["diagnostic"])
    (output_dir / "QM_FORBIDDEN_CLAIMS.md").write_text(forbidden_claim_markdown(), encoding="utf-8")
