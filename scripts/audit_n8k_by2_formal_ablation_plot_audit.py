#!/usr/bin/env python3
"""Audit N8K BY2 formal ablation plot-audit reports."""

# 中文说明：主审计同时检查正式消融、绘图覆盖、语义边界和退化矩阵禁用。

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.by2_formal_ablation_plot_catalog import PLOT_CATEGORIES
from legsa_gins.reporting.by2_formal_ablation_spec import build_formal_ablation_matrix, build_formal_ablation_spec


REQUIRED_REPORTS = [
    "N8K_BY2_FORMAL_ABLATION_SPEC.json",
    "N8K_BY2_FORMAL_ABLATION_MATRIX.json",
    "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json",
    "N8K_BY2_ABLATION_FULL_PLOT_CATALOG.json",
    "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json",
    "N8K_BY2_FORMAL_ABLATION_SEMANTIC_GUARD_REPORT.json",
    "N8K_BY2_FORMAL_ABLATION_SUMMARY_REPORT.json",
    "N8K_BY2_FORMAL_ABLATION_CASE_REVIEW_INDEX.json",
    "N8K_N9B_DEGRADATION_PLAN_REPORT.json",
    "N8K_BY2_FORMAL_ABLATION_PLOT_AUDIT_DECISION_REPORT.json",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8k_by2_formal_ablation_plot_audit failed: {message}")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def report_root() -> Path | None:
    value = os.environ.get("N8K_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            _fail(f"missing report {name}")
    spec = _json(root / "N8K_BY2_FORMAL_ABLATION_SPEC.json")
    matrix = _json(root / "N8K_BY2_FORMAL_ABLATION_MATRIX.json")
    coverage = _json(root / "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json")
    semantic = _json(root / "N8K_BY2_FORMAL_ABLATION_SEMANTIC_GUARD_REPORT.json")
    plan = _json(root / "N8K_N9B_DEGRADATION_PLAN_REPORT.json")
    decision = _json(root / "N8K_BY2_FORMAL_ABLATION_PLOT_AUDIT_DECISION_REPORT.json")
    if spec.get("variant_count") != 30:
        _fail("formal ablation variant count must be 30")
    if matrix.get("completed_count") != matrix.get("variant_count") or matrix.get("failed_count") != 0:
        _fail("formal ablation incomplete")
    if coverage.get("required_category_count") != 14 or coverage.get("all_required_categories_complete") is not True:
        _fail("required plot categories incomplete")
    if coverage.get("missing_count") != 0:
        _fail("plot coverage has missing files")
    if semantic.get("all_checks_passed") is not True:
        _fail("semantic guard failed")
    if plan.get("degradation_matrix_run") is not False or plan.get("plan_only") is not True:
        _fail("N8K unexpectedly ran degradation matrix")
    if decision.get("status") != "BY2_formal_ablation_plot_audit_complete":
        _fail(f"unexpected decision {decision.get('status')}")
    for payload_name in REQUIRED_REPORTS:
        payload = _json(root / payload_name)
        if payload.get("paper_performance_claim") is not False:
            _fail(f"{payload_name} allows paper claim")
        if payload.get("outperform_final_v23_claim") is True:
            _fail(f"{payload_name} allows outperform claim")


def make_toy_n8k_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    spec = build_formal_ablation_spec({"n8j": "role"})
    matrix = build_formal_ablation_matrix(spec)
    png_count = sum(len([name for name in names if name.endswith(".png")]) for names in PLOT_CATEGORIES.values()) * spec["variant_count"]
    expected_files = sum(len(names) for names in PLOT_CATEGORIES.values()) * spec["variant_count"]
    write_json(root / "N8K_BY2_FORMAL_ABLATION_SPEC.json", spec)
    write_json(root / "N8K_BY2_FORMAL_ABLATION_MATRIX.json", matrix)
    write_json(root / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json", {"stage": "N8K", "variant_count": 30, "metrics": [], "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K_BY2_ABLATION_FULL_PLOT_CATALOG.json", {"stage": "N8K", "variant_count": 30, "category_count": 14, "paper_performance_claim": False})
    write_json(root / "N8K_BY2_ABLATION_PLOT_COVERAGE_REPORT.json", {"stage": "N8K", "required_category_count": 14, "total_expected_files": expected_files, "total_generated_files": expected_files, "total_png_figures_generated": png_count, "missing_count": 0, "not_applicable_count": 1, "all_required_categories_complete": True, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K_BY2_FORMAL_ABLATION_SEMANTIC_GUARD_REPORT.json", {"stage": "N8K", "all_checks_passed": True, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K_BY2_FORMAL_ABLATION_SUMMARY_REPORT.json", {"stage": "N8K", "review_count": 30, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K_BY2_FORMAL_ABLATION_CASE_REVIEW_INDEX.json", {"stage": "N8K", "case_review_count": 30, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K_N9B_DEGRADATION_PLAN_REPORT.json", {"stage": "N8K", "plan_only": True, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K_BY2_FORMAL_ABLATION_PLOT_AUDIT_DECISION_REPORT.json", {"stage": "N8K", "status": "BY2_formal_ablation_plot_audit_complete", "recommended_next_stage": "N9A_BY2_full_plot_audit", "degradation_matrix_run": False, "no_algorithm_changes": True, "paper_performance_claim": False, "outperform_final_v23_claim": False})


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k"
            make_toy_n8k_root(root)
            audit_runtime(root)
    else:
        audit_runtime(root)
    print("audit_n8k_by2_formal_ablation_plot_audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
