"""N8E claim-boundary review.

中文说明：扫描 N8E 文档和报告中的越界 claim，并保留否定语境。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


NEGATION_TOKENS = [
    "no ",
    "not ",
    "does not ",
    "do not ",
    "never ",
    "without ",
    "diagnostic only",
    "diagnostic-only",
    "evaluation-only",
    "caveat",
    "blocked",
    "forbidden",
    "any claim that",
    "any unqualified",
    "must not",
]

FORBIDDEN_CLAIM_PATTERNS = [
    ("outperform_final_v23", re.compile(r"\boutperform(?:s|ed|ing)?\s+final_v23\b", re.IGNORECASE)),
    ("paper_performance_claim", re.compile(r"\bpaper\s+performance\s+claim\b|\bformal\s+paper\s+performance\b", re.IGNORECASE)),
    ("trace_tuned", re.compile(r"\btrace[-_\s]*(?:tuned|tuning)\b|\btuned\s+(?:with|by|using)?\s*trace\b", re.IGNORECASE)),
    ("final_v23_tuned", re.compile(r"\bfinal_v23[-_\s]*(?:tuned|tuning)\b|\btuned\s+(?:with|by|using)?\s*final_v23\b", re.IGNORECASE)),
    ("fgo_feedback", re.compile(r"\bfgo\s+(?:output\s+)?(?:feedback|feeds?\s+back|fed\s+back)\b|\bfeedback\s+to\s+ekf\b", re.IGNORECASE)),
    ("fgo_replaces_ekf", re.compile(r"\bfgo\s+(?:output\s+)?replaces?\s+ekf\b|\breplaces?\s+ekf\s+nav\b", re.IGNORECASE)),
    ("go2_truth", re.compile(r"\bgo2\b.{0,40}\btruth\b", re.IGNORECASE | re.DOTALL)),
    ("unsupported_rtk_fixed", re.compile(r"\brtk\s+fixed\s+claim\b|\brtk\s+fixed\s+solution\b", re.IGNORECASE)),
    ("raw_doppler_raw_tight_coupling", re.compile(r"\braw\s+doppler\b.{0,60}\braw\s+tight\s+coupling\b", re.IGNORECASE | re.DOTALL)),
    ("candidate_factor_formal", re.compile(r"\bcandidate\s+factors?\b.{0,60}\bformal\s+factor\b|\bformal\s+candidate\s+factors?\b", re.IGNORECASE | re.DOTALL)),
]


def _safe_context(text: str, start: int, end: int, radius: int = 90) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def _is_negated(context: str) -> bool:
    lowered = re.sub(r"\s+", " ", context.lower())
    return any(token in lowered for token in NEGATION_TOKENS)


def review_claim_texts(text_sources: dict[str, str]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    ignored_negated: list[dict[str, Any]] = []
    for source, text in text_sources.items():
        for claim_id, pattern in FORBIDDEN_CLAIM_PATTERNS:
            for match in pattern.finditer(text):
                context = _safe_context(text, match.start(), match.end())
                item = {
                    "claim_id": claim_id,
                    "source": source,
                    "match": match.group(0),
                    "context": re.sub(r"\s+", " ", context).strip(),
                }
                if _is_negated(context):
                    ignored_negated.append(item)
                else:
                    findings.append(item)
    return {
        "stage": "N8E_formal_engineering_ablation_with_caveat",
        "forbidden_claims_found": findings,
        "forbidden_claim_count": len(findings),
        "ignored_negated_claim_mentions": ignored_negated[:50],
        "ignored_negated_claim_count": len(ignored_negated),
        "decision": "block" if findings else "pass",
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": not any(row["claim_id"] == "outperform_final_v23" for row in findings),
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_substitution": False,
    }


def collect_claim_review_sources(
    *,
    docs_root: str | Path,
    report_root: str | Path | None = None,
) -> dict[str, str]:
    docs_root = Path(docs_root)
    sources: dict[str, str] = {}
    for base in [docs_root / "experiments", docs_root / "codex_prompts"]:
        if not base.exists():
            continue
        for path in sorted(base.glob("n8e*.md")) + sorted(base.glob("N8E*.md")):
            sources[str(path.relative_to(docs_root.parent))] = path.read_text(encoding="utf-8")
    boundary = docs_root.parent / "CLAIM_BOUNDARY.md"
    if boundary.exists():
        text = boundary.read_text(encoding="utf-8")
        marker = "## N8E Formal Engineering Ablation Boundary"
        if marker in text:
            start = text.index(marker)
            next_section = text.find("\n## ", start + len(marker))
            sources["CLAIM_BOUNDARY.md#N8E"] = text[start : next_section if next_section >= 0 else len(text)]
        else:
            sources["CLAIM_BOUNDARY.md"] = text
    if report_root:
        root = Path(report_root)
        if root.exists():
            for path in sorted(root.glob("N8E_*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                sources[f"N8E_REPORT_OUTPUT_DIR/{path.name}"] = json.dumps(payload, indent=2, sort_keys=True)
            review = root / "n8e_formal_ablation_case_review.md"
            if review.exists():
                sources[f"N8E_REPORT_OUTPUT_DIR/{review.name}"] = review.read_text(encoding="utf-8")
    return sources


def review_claim_boundaries(
    *,
    docs_root: str | Path,
    report_root: str | Path | None = None,
) -> dict[str, Any]:
    return review_claim_texts(collect_claim_review_sources(docs_root=docs_root, report_root=report_root))
