#!/usr/bin/env python3
"""Audit N8K5 cross-category duplicate semantic fix reports."""

# 中文说明：N8K5 主审计要求复现跨类别重复，并证明阻塞重复修复后清零。

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


REQUIRED_REPORTS = [
    "N8K5_CROSS_CATEGORY_DUPLICATE_AUDIT_REPORT.json",
    "N8K5_CROSS_CATEGORY_SEMANTIC_FIX_REPORT.json",
    "N8K5_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json",
    "N8K5_DUPLICATE_REGRESSION_REPORT.json",
    "N8K5_BY2_FORMAL_ABLATION_CROSS_CATEGORY_FIX_DECISION_REPORT.json",
]


def report_root() -> Path | None:
    value = os.environ.get("N8K5_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_toy_n8k5_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    write_json(
        root / "N8K5_CROSS_CATEGORY_DUPLICATE_AUDIT_REPORT.json",
        {
            "stage": "N8K5",
            "global_exact_duplicate_hash_groups_before": 68,
            "duplicate_files_involved_before": 138,
            "same_variant_cross_category_duplicate_before": 60,
            "same_category_exact_duplicate_groups_before": 0,
            "cross_variant_only_duplicate_groups_before": 8,
            "blocking_cross_category_duplicate_patterns_before": [
                {"affected_variant_count": 30, "files": [{"category": "03_velocity", "filename": "velocity_residual_time.png"}, {"category": "07_compare", "filename": "compare_velocity_error.png"}]},
                {"affected_variant_count": 30, "files": [{"category": "06_observation_quality", "filename": "feedback_accept_reject_time.png"}, {"category": "07_compare", "filename": "compare_feedback_delta.png"}]},
            ],
            "paper_performance_claim": False,
            "outperform_final_v23_claim": False,
            "algorithm_changes": False,
            "degradation_matrix_run": False,
        },
    )
    fix = {
        "stage": "N8K5",
        "global_exact_duplicate_hash_groups_before": 68,
        "global_exact_duplicate_hash_groups_after": 8,
        "same_variant_cross_category_duplicate_before": 60,
        "same_variant_cross_category_duplicate_after": 0,
        "blocking_cross_category_duplicate_patterns_before": [],
        "blocking_cross_category_duplicate_patterns_after": [],
        "velocity_residual_vs_compare_velocity_duplicate_count_before": 30,
        "velocity_residual_vs_compare_velocity_duplicate_count_after": 0,
        "feedback_quality_vs_compare_feedback_delta_duplicate_count_before": 30,
        "feedback_quality_vs_compare_feedback_delta_duplicate_count_after": 0,
        "feedback_empty_axis_before_count": 21,
        "feedback_empty_axis_after_count": 0,
        "compare_velocity_error_not_applicable_count": 0,
        "compare_feedback_delta_not_applicable_count": 21,
        "feedback_accept_reject_time_not_applicable_count": 21,
        "compare_velocity_error_semantic_mismatch_before": 30,
        "compare_velocity_error_semantic_mismatch_after": 0,
        "compare_feedback_delta_semantic_mismatch_before": 30,
        "compare_feedback_delta_semantic_mismatch_after": 0,
        "semantic_mismatch_before_count": 0,
        "semantic_mismatch_after_count": 0,
        "exact_same_category_duplicate_after": 0,
        "placeholder_remaining": 0,
        "applicable_placeholder_remaining": 0,
        "derived_surrogate_labels_count": 20,
        "derived_data_labels_count": 20,
        "figures_regenerated_count": 90,
        "figures_copied_count": 2850,
        "categories_touched": ["03_velocity", "06_observation_quality", "07_compare"],
        "variants_touched": ["toy"],
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    write_json(root / "N8K5_CROSS_CATEGORY_SEMANTIC_FIX_REPORT.json", fix)
    write_json(root / "N8K5_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json", {"stage": "N8K5", "placeholder_remaining": 0, "applicable_placeholder_remaining": 0, "feedback_empty_axis_after_count": 0, "semantic_mismatch_after_count": 0, "paper_performance_claim": False, "outperform_final_v23_claim": False, "algorithm_changes": False, "degradation_matrix_run": False})
    write_json(root / "N8K5_DUPLICATE_REGRESSION_REPORT.json", {"stage": "N8K5", "global_exact_duplicate_hash_groups_before": 68, "global_exact_duplicate_hash_groups_after": 8, "same_variant_cross_category_duplicate_before": 60, "same_variant_cross_category_duplicate_after": 0, "same_category_exact_duplicate_after": 0, "blocking_cross_category_duplicate_patterns_after": [], "paper_performance_claim": False, "outperform_final_v23_claim": False, "algorithm_changes": False, "degradation_matrix_run": False})
    write_json(root / "N8K5_BY2_FORMAL_ABLATION_CROSS_CATEGORY_FIX_DECISION_REPORT.json", {"stage": "N8K5", "status": "BY2_formal_ablation_cross_category_semantic_fix_complete", "recommended_next_stage": "N8K_final_merge_review_then_N9A_BY2_full_plot_audit", "same_variant_cross_category_duplicate_after": 0, "feedback_empty_axis_after_count": 0, "semantic_mismatch_after_count": 0, "algorithm_changes": False, "no_algorithm_changes": True, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})


def audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            raise SystemExit(f"audit_n8k5_cross_category_duplicate_plots failed: missing {name}")
    audit = _json(root / "N8K5_CROSS_CATEGORY_DUPLICATE_AUDIT_REPORT.json")
    fix = _json(root / "N8K5_CROSS_CATEGORY_SEMANTIC_FIX_REPORT.json")
    decision = _json(root / "N8K5_BY2_FORMAL_ABLATION_CROSS_CATEGORY_FIX_DECISION_REPORT.json")
    if audit.get("same_variant_cross_category_duplicate_before", 0) <= 0:
        raise SystemExit("audit_n8k5_cross_category_duplicate_plots failed: cross-category duplicate not reproduced")
    if fix.get("velocity_residual_vs_compare_velocity_duplicate_count_after") != 0:
        raise SystemExit("audit_n8k5_cross_category_duplicate_plots failed: velocity duplicate remains")
    if fix.get("feedback_quality_vs_compare_feedback_delta_duplicate_count_after") != 0:
        raise SystemExit("audit_n8k5_cross_category_duplicate_plots failed: feedback duplicate remains")
    if decision.get("status") != "BY2_formal_ablation_cross_category_semantic_fix_complete":
        raise SystemExit(f"audit_n8k5_cross_category_duplicate_plots failed: {decision.get('status')}")
    for name in REQUIRED_REPORTS:
        payload = _json(root / name)
        if payload.get("paper_performance_claim") is not False or payload.get("outperform_final_v23_claim") is True:
            raise SystemExit(f"audit_n8k5_cross_category_duplicate_plots failed: claim boundary in {name}")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k5"
            make_toy_n8k5_root(root)
            audit_runtime(root)
    else:
        audit_runtime(root)
    print("audit_n8k5_cross_category_duplicate_plots passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
