"""N8K BY2 formal ablation case review generation."""

# 中文说明：case review 是工程审计材料，不作为论文性能结论。

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


def build_case_reviews(matrix: dict[str, Any], metrics_report: dict[str, Any], case_review_dir: str | Path, summary_dir: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    case_root = Path(case_review_dir)
    summary_root = Path(summary_dir)
    case_root.mkdir(parents=True, exist_ok=True)
    summary_root.mkdir(parents=True, exist_ok=True)
    metric_by_variant = {item.get("variant_id"): item for item in metrics_report.get("metrics", [])}
    reviews = []
    for row in matrix.get("rows", []):
        variant_id = row["variant_id"]
        metrics = metric_by_variant.get(variant_id, {})
        path = case_root / variant_id / "case_review.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# {variant_id}",
            "",
            f"- group: `{row.get('group')}`",
            f"- run status: `{row.get('run_status')}`",
            f"- horizontal p95: `{metrics.get('horizontal_p95')}`",
            f"- yaw p95: `{metrics.get('yaw_p95')}`",
            "- suitability: `internal_audit_only`",
            "- caveat: BY2 formal ablation audit only, no paper performance claim.",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        reviews.append({"variant_id": variant_id, "path_role": "N8K_CASE_REVIEW_DIR", "figure_suitability": "internal_audit_only", "present": True})
    summary_report = {
        "stage": "N8K",
        "review_count": len(reviews),
        "case_reviews": reviews,
        "recommended_figures": ["compare_core_metrics.png", "ablation_metric_heatmap_horizontal.png", "n8k decision panel"],
        "figure_suitability_counts": {"internal_audit_only": len(reviews), "paper_candidate": 0, "redraw_for_paper": 0, "direct_use_possible": 0},
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    index = {
        "stage": "N8K",
        "case_review_count": len(reviews),
        "case_reviews": reviews,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    (summary_root / "N8K_BY2_FORMAL_ABLATION_SUMMARY.md").write_text(
        "# N8K BY2 Formal Ablation Summary\n\n"
        f"- variants: `{len(reviews)}`\n"
        "- scope: formal ablation plot audit only\n"
        "- no full degradation matrix run\n"
        "- no paper performance claim\n",
        encoding="utf-8",
    )
    return summary_report, index


def write_case_review_reports(output_dir: str | Path, summary_report: dict[str, Any], index: dict[str, Any]) -> None:
    root = Path(output_dir)
    write_json(root / "N8K_BY2_FORMAL_ABLATION_SUMMARY_REPORT.json", summary_report)
    write_json(root / "N8K_BY2_FORMAL_ABLATION_CASE_REVIEW_INDEX.json", index)
