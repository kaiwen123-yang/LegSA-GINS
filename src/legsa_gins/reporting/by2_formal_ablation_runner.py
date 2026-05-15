"""N8K BY2 formal ablation plot-audit orchestration helpers."""

# 中文说明：runner 只编排报告和绘图，不改 solver、gate 或 covariance。

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, write_json

from .by2_degradation_plan_for_n9b import build_n9b_degradation_plan
from .by2_formal_ablation_case_review import build_case_reviews, write_case_review_reports
from .by2_formal_ablation_decision import build_n8k_decision
from .by2_formal_ablation_metrics import build_formal_ablation_metrics, write_matrix_table, write_metrics_table
from .by2_formal_ablation_plot_catalog import build_plot_catalog
from .by2_formal_ablation_plot_coverage import build_plot_coverage
from .by2_formal_ablation_plot_generator import generate_ablation_plots
from .by2_formal_ablation_semantic_guard import build_semantic_guard
from .by2_formal_ablation_spec import build_formal_ablation_matrix, build_formal_ablation_spec


def run_n8k_formal_ablation_plot_audit(
    *,
    previous_roots: dict[str, str],
    plot_audit_root: str | Path,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    case_review_dir: str | Path,
    summary_dir: str | Path,
    allow_run: bool,
) -> dict[str, Any]:
    if not allow_run:
        raise RuntimeError("--allow-run is required for N8K formal ablation plot audit")
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    n8j_root = Path(previous_roots["n8j"])
    n8j_policy = read_json(n8j_root / "N8J_SELECTED_FEEDBACK_POLICY_REPORT.json")
    if n8j_policy.get("n8i_selected_policy_match") is not True or n8j_policy.get("hidden_policy_change") is True:
        raise RuntimeError("N8J selected policy is not locked")
    spec = build_formal_ablation_spec(previous_roots)
    matrix = build_formal_ablation_matrix(spec)
    metrics = build_formal_ablation_metrics(matrix, n8j_root)
    catalog = build_plot_catalog(matrix)
    generation = generate_ablation_plots(catalog, matrix, metrics, figure_output_dir)
    coverage = build_plot_coverage(catalog, generation, figure_output_dir)
    semantic_guard = build_semantic_guard(matrix, coverage, plot_audit_root, figure_output_dir)
    summary_report, case_index = build_case_reviews(matrix, metrics, case_review_dir, summary_dir)
    degradation_plan = build_n9b_degradation_plan()
    decision = build_n8k_decision(matrix, coverage, semantic_guard, degradation_plan)
    write_json(output_root / "N8K_BY2_FORMAL_ABLATION_SPEC.json", spec)
    write_json(output_root / "N8K_BY2_FORMAL_ABLATION_MATRIX.json", matrix)
    write_metrics_table(output_root / "N8K_BY2_FORMAL_ABLATION_METRICS_TABLE.csv", metrics["metrics"])
    write_matrix_table(output_root / "N8K_BY2_FORMAL_ABLATION_TABLE.csv", matrix["rows"])
    write_json(output_root / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json", metrics)
    write_json(output_root / "N8K_BY2_ABLATION_FULL_PLOT_CATALOG.json", catalog)
    write_json(output_root / "N8K_BY2_ABLATION_PLOT_GENERATION_MANIFEST.json", generation)
    write_json(output_root / "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json", coverage)
    write_json(output_root / "N8K_BY2_FORMAL_ABLATION_SEMANTIC_GUARD_REPORT.json", semantic_guard)
    write_case_review_reports(output_root, summary_report, case_index)
    write_json(output_root / "N8K_N9B_DEGRADATION_PLAN_REPORT.json", degradation_plan)
    write_json(output_root / "N8K_BY2_FORMAL_ABLATION_PLOT_AUDIT_DECISION_REPORT.json", decision)
    _write_case_review(output_root / "n8k_by2_formal_ablation_plot_audit_case_review.md", decision, matrix, coverage)
    return {
        "stage": "N8K",
        "status": decision["status"],
        "recommended_next_stage": decision["recommended_next_stage"],
        "variant_count": matrix["variant_count"],
        "completed_count": matrix["completed_count"],
        "failed_count": matrix["failed_count"],
        "total_figures_generated": coverage["total_png_figures_generated"],
        "missing_plot_count": coverage["missing_count"],
        "not_applicable_count": coverage["not_applicable_count"],
        "case_review_count": summary_report["review_count"],
        "degradation_matrix_run": False,
        "no_algorithm_changes": True,
        "paper_performance_claim": False,
    }


def _write_case_review(path: Path, decision: dict[str, Any], matrix: dict[str, Any], coverage: dict[str, Any]) -> None:
    path.write_text(
        "# N8K BY2 Formal Ablation Plot Audit Case Review\n\n"
        f"- decision: `{decision.get('status')}`\n"
        f"- variants: `{matrix.get('variant_count')}`\n"
        f"- completed/failed: `{matrix.get('completed_count')}` / `{matrix.get('failed_count')}`\n"
        f"- figures: `{coverage.get('total_png_figures_generated')}`\n"
        f"- missing plots: `{coverage.get('missing_count')}`\n"
        "- scope: formal ablation plot audit only; no full degradation matrix run.\n"
        "- boundary: no algorithm changes, no trace/final_v23 tuning, no paper performance claim.\n",
        encoding="utf-8",
    )
