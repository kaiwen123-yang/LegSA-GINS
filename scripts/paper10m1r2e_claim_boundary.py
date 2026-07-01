#!/usr/bin/env python3
"""Claim-boundary helpers for PAPER10M1R2E.

This module is intentionally review-only. It contains bounded wording for the
BY2 yaw-corrected full-algorithm and internal-ablation evidence and exposes
small table writers used by the M1R2E result-review script.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable


INTERPRETATION_LABELS = {
    "strong_positive_evidence",
    "moderate_positive_evidence",
    "weak_positive_evidence",
    "neutral_no_effect",
    "tradeoff",
    "negative_or_hurts",
    "alias_or_duplicate",
    "diagnostic_only",
    "not_claimable",
}


FORBIDDEN_CLAIM_KEYS = [
    "universal_superiority",
    "final_paper_claim_ready",
    "by3_yaw_generalization",
    "xb_high_precision_severe_gnss_proof",
    "exact_external_reproduction",
    "complete_9f_fgo_validated",
    "go2_truth",
    "output_only_correction",
    "per_case_tuning",
    "deleting_bad_epochs",
    "old_m1r2c_yaw_invalid_result",
    "legacy_bad_a1_consumed_count_claim",
    "final_v23_comprehensive_superiority",
    "all_modules_significantly_improve",
    "go2_joint_effective_when_zero_delta",
    "fgo_feedback_effective_when_zero_delta",
]


def claim_rows() -> dict[str, list[dict[str, str]]]:
    """Return frozen claim-boundary rows grouped by paper location."""

    allowed = [
        {
            "claim_id": "A01",
            "claim_en": "BY2 controlled degradation matrix was completed with yaw-corrected providers.",
            "claim_cn": "BY2受控退化矩阵已基于修正航向provider完成。",
            "evidence_source": "M1R2A,M1R2B2,M1R2C_R1,M1R2D_R1",
            "boundary": "BY2 only; no final paper readiness claim.",
        },
        {
            "claim_id": "A02",
            "claim_en": "Four frozen full-algorithm modes completed 2164 evaluable BY2 runs.",
            "claim_cn": "四种冻结完整算法模式完成2164行可评估BY2运行。",
            "evidence_source": "M1R2C_R1 row and method summaries",
            "boundary": "Old yaw-invalid M1R2C metrics are excluded.",
        },
        {
            "claim_id": "A03",
            "claim_en": "Nine internal ablation methods completed 4869 evaluable BY2 runs.",
            "claim_cn": "九种内部消融方法完成4869行可评估BY2运行。",
            "evidence_source": "M1R2D_R1 row and method summaries",
            "boundary": "No M1R2C_R1 row substitution.",
        },
        {
            "claim_id": "A04",
            "claim_en": "Trace was used as evaluation-only reference, not as solver input.",
            "claim_cn": "Trace只作为离线评估参考，没有作为求解器输入。",
            "evidence_source": "M1R2C_R1/M1R2D_R1 row-level forbidden-input fields",
            "boundary": "No trace online and no trace tuning.",
        },
    ]
    conditional = [
        {
            "claim_id": "C01",
            "claim_en": "Raw Doppler shows a small bounded auxiliary contribution under the frozen BY2 protocol.",
            "claim_cn": "Raw Doppler在冻结BY2协议下呈现小幅、有边界的辅助贡献。",
            "condition": "Use small/stable/bounded wording only.",
            "forbidden_upgrade": "Do not claim large or universal improvement.",
        },
        {
            "claim_id": "C02",
            "claim_en": "Source-aware weighting shows stable bounded contribution in many BY2 cases.",
            "claim_cn": "来源感知权重在许多BY2工况中体现稳定但有边界的贡献。",
            "condition": "Mention small delta and metric tradeoffs.",
            "forbidden_upgrade": "Do not claim comprehensive performance superiority.",
        },
        {
            "claim_id": "C03",
            "claim_en": "Multi-state QM provides interpretable state/action traces but exhibits metric tradeoffs.",
            "claim_cn": "多状态QM提供可解释的状态/动作轨迹，但存在指标权衡。",
            "condition": "Discuss as mechanism evidence, not as all-metric performance gain.",
            "forbidden_upgrade": "Do not write that QM comprehensively improves results.",
        },
        {
            "claim_id": "C04",
            "claim_en": "Go2 horizontal velocity is a weak auxiliary prior with limited measured contribution.",
            "claim_cn": "Go2水平速度是弱辅助先验，实测贡献有限。",
            "condition": "Keep weak-prior wording and never treat Go2 as truth.",
            "forbidden_upgrade": "Do not claim Go2 pose, velocity, contact, or yaw truth.",
        },
    ]
    appendix = [
        {
            "claim_id": "P01",
            "claim_en": "Run completeness, render QA, and forbidden-input audits support execution validity.",
            "claim_cn": "运行完整性、渲染QA和禁用输入审计支持执行有效性。",
            "paper_location": "appendix",
            "boundary": "These are validity audits, not method-novelty claims.",
        },
        {
            "claim_id": "P02",
            "claim_en": "D30-D41 yaw-family and D58-D60 mixed/recovery panels are bounded sanity checks.",
            "claim_cn": "D30-D41航向族和D58-D60混合/恢复面板是有边界的 sanity check。",
            "paper_location": "appendix_or_representative_main",
            "boundary": "Do not generalize to BY3 yaw.",
        },
    ]
    diagnostic = [
        {
            "claim_id": "D01",
            "claim_en": "Go2 joint/proprioceptive factor has no measured delta in this matrix.",
            "claim_cn": "Go2关节/本体因子在本矩阵中没有可测delta。",
            "diagnostic_reason": "zero delta; same-order count equals all cases",
        },
        {
            "claim_id": "D02",
            "claim_en": "FGO feedback / EKF-only relation has no measured delta in this matrix.",
            "claim_cn": "FGO反馈/EKF-only关系在本矩阵中没有可测delta。",
            "diagnostic_reason": "current alias/no-effect under frozen policy",
        },
        {
            "claim_id": "D03",
            "claim_en": "Legacy bad-A1 consumed counters are not claim fields.",
            "claim_cn": "旧版bad-A1 consumed计数不是可写claim字段。",
            "diagnostic_reason": "deprecated semantic field",
        },
    ]
    return {
        "allowed": allowed,
        "conditional": conditional,
        "appendix": appendix,
        "diagnostic": diagnostic,
    }


def forbidden_claim_markdown() -> str:
    lines = [
        "# PAPER10M1R2E Forbidden Claims",
        "",
        "The following claim families are frozen as forbidden for M1R2E.",
        "",
    ]
    wording = {
        "universal_superiority": "Do not claim universal superiority.",
        "final_paper_claim_ready": "Do not claim final paper claim readiness.",
        "by3_yaw_generalization": "Do not claim BY3 yaw generalization.",
        "xb_high_precision_severe_gnss_proof": "Do not claim severe-GNSS high-precision proof for XB/PG.",
        "exact_external_reproduction": "Do not claim exact external reproduction.",
        "complete_9f_fgo_validated": "Do not claim complete 9F FGO validation.",
        "go2_truth": "Do not treat Go2 position, velocity, contact, or yaw as truth.",
        "output_only_correction": "Do not perform or claim output-only correction.",
        "per_case_tuning": "Do not tune per case.",
        "deleting_bad_epochs": "Do not delete bad epochs to pass metrics.",
        "old_m1r2c_yaw_invalid_result": "Do not use old M1R2C yaw-invalid metrics as valid evidence.",
        "legacy_bad_a1_consumed_count_claim": "Do not use legacy bad-A1 consumed counters as claim fields.",
        "final_v23_comprehensive_superiority": "Do not claim comprehensive superiority over final_v23.",
        "all_modules_significantly_improve": "Do not claim all modules significantly improve performance.",
        "go2_joint_effective_when_zero_delta": "Do not claim Go2 joint effectiveness when measured delta is zero.",
        "fgo_feedback_effective_when_zero_delta": "Do not claim FGO feedback effectiveness when measured delta is zero.",
    }
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
    write_csv(output_dir / "PAPER10M1R2E_ALLOWED_CLAIMS.csv", rows["allowed"])
    write_csv(output_dir / "PAPER10M1R2E_CONDITIONAL_CLAIMS.csv", rows["conditional"])
    write_csv(output_dir / "PAPER10M1R2E_APPENDIX_ONLY_CLAIMS.csv", rows["appendix"])
    write_csv(output_dir / "PAPER10M1R2E_DIAGNOSTIC_ONLY_CLAIMS.csv", rows["diagnostic"])
    (output_dir / "PAPER10M1R2E_FORBIDDEN_CLAIMS.md").write_text(
        forbidden_claim_markdown(), encoding="utf-8"
    )
