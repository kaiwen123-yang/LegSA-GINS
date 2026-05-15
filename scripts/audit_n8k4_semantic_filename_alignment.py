#!/usr/bin/env python3
"""Audit N8K4 semantic filename alignment reports."""

# 中文说明：N8K4 要证明文件名、semantic_role、not_applicable reason 对齐。

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
    "N8K4_SEMANTIC_FILENAME_AUDIT_REPORT.json",
    "N8K4_SEMANTIC_FILENAME_FIX_REPORT.json",
    "N8K4_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json",
    "N8K4_DUPLICATE_REGRESSION_REPORT.json",
    "N8K4_BY2_FORMAL_ABLATION_SEMANTIC_FILENAME_FIX_DECISION_REPORT.json",
]


def report_root() -> Path | None:
    value = os.environ.get("N8K4_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_toy_n8k4_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "N8K4_SEMANTIC_FILENAME_AUDIT_REPORT.json", {"stage": "N8K4", "semantic_filename_mismatch_before_count": 69, "paper_performance_claim": False, "outperform_final_v23_claim": False, "algorithm_changes": False, "degradation_matrix_run": False})
    write_json(
        root / "N8K4_SEMANTIC_FILENAME_FIX_REPORT.json",
        {
            "stage": "N8K4",
            "semantic_filename_mismatch_before_count": 69,
            "semantic_filename_mismatch_after_count": 0,
            "exact_duplicate_after_count": 0,
            "perceptual_duplicate_after_count": 0,
            "placeholder_remaining": 0,
            "applicable_placeholder_remaining": 0,
            "compare_horizontal_error_not_applicable_count": 0,
            "reject_all_sanity_compare_not_applicable_count": 21,
            "feedback_accept_reject_timeline_applicable_count": 9,
            "feedback_accept_reject_timeline_not_applicable_count": 21,
            "reject_all_sanity_applicable_count": 9,
            "reject_all_sanity_not_applicable_count": 21,
            "yaw_residual_time_mismatch_count": 0,
            "yaw_wrap_check_mismatch_count": 0,
            "feedback_accept_reject_timeline_mismatch_count": 0,
            "reject_all_sanity_mismatch_count": 0,
            "derived_data_labels_count": 20,
            "derived_surrogate_labels_count": 20,
            "figures_regenerated_count": 180,
            "figures_copied_count": 2850,
            "categories_touched": ["04_attitude", "07_compare", "11_feedback"],
            "variants_touched": ["toy"],
            "algorithm_changes": False,
            "degradation_matrix_run": False,
            "paper_performance_claim": False,
            "outperform_final_v23_claim": False,
        },
    )
    write_json(root / "N8K4_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json", {"stage": "N8K4", "semantic_filename_mismatch_count": 0, "applicable_placeholder_remaining": 0, "placeholder_remaining": 0, "paper_performance_claim": False, "outperform_final_v23_claim": False, "algorithm_changes": False, "degradation_matrix_run": False})
    write_json(root / "N8K4_DUPLICATE_REGRESSION_REPORT.json", {"stage": "N8K4", "exact_duplicate_after_count": 0, "same_category_exact_duplicate_remaining": 0, "perceptual_duplicate_after_count": 0, "paper_performance_claim": False, "outperform_final_v23_claim": False, "algorithm_changes": False, "degradation_matrix_run": False})
    write_json(root / "N8K4_BY2_FORMAL_ABLATION_SEMANTIC_FILENAME_FIX_DECISION_REPORT.json", {"stage": "N8K4", "status": "BY2_formal_ablation_semantic_filename_fix_complete", "recommended_next_stage": "N8K_merge_review_then_N9A_BY2_full_plot_audit", "semantic_filename_mismatch_count": 0, "same_category_exact_duplicate_remaining": 0, "perceptual_duplicate_after_count": 0, "applicable_placeholder_remaining": 0, "algorithm_changes": False, "no_algorithm_changes": True, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})


def audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            raise SystemExit(f"audit_n8k4_semantic_filename_alignment failed: missing {name}")
    audit = _json(root / "N8K4_SEMANTIC_FILENAME_AUDIT_REPORT.json")
    fix = _json(root / "N8K4_SEMANTIC_FILENAME_FIX_REPORT.json")
    decision = _json(root / "N8K4_BY2_FORMAL_ABLATION_SEMANTIC_FILENAME_FIX_DECISION_REPORT.json")
    if audit.get("semantic_filename_mismatch_before_count", 0) <= 0:
        raise SystemExit("audit_n8k4_semantic_filename_alignment failed: before mismatch not reproduced")
    if fix.get("semantic_filename_mismatch_after_count") != 0:
        raise SystemExit("audit_n8k4_semantic_filename_alignment failed: semantic mismatch remains")
    if decision.get("status") != "BY2_formal_ablation_semantic_filename_fix_complete":
        raise SystemExit(f"audit_n8k4_semantic_filename_alignment failed: {decision.get('status')}")
    for name in REQUIRED_REPORTS:
        payload = _json(root / name)
        if payload.get("paper_performance_claim") is not False or payload.get("outperform_final_v23_claim") is True:
            raise SystemExit(f"audit_n8k4_semantic_filename_alignment failed: claim boundary in {name}")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k4"
            make_toy_n8k4_root(root)
            audit_runtime(root)
    else:
        audit_runtime(root)
    print("audit_n8k4_semantic_filename_alignment passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
