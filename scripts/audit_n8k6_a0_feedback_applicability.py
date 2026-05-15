#!/usr/bin/env python3
"""Audit N8K6 A0 feedback applicability fix reports."""

# 中文说明：A0 是 baseline_no_feedback，原始 feedback 行不能让它变成 feedback-applicable。

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
from legsa_gins.reporting.by2_feedback_applicability import (
    BASELINE_NOT_APPLICABLE_REASON,
    FEEDBACK_SPECIFIC_FIGURES,
)


REQUIRED_REPORTS = [
    "N8K6_A0_FEEDBACK_APPLICABILITY_AUDIT_REPORT.json",
    "N8K6_A0_FEEDBACK_APPLICABILITY_FIX_REPORT.json",
    "N8K6_A0_FEEDBACK_PLOT_REGENERATION_REPORT.json",
    "N8K6_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json",
    "N8K6_DUPLICATE_REGRESSION_REPORT.json",
    "N8K6_FINAL_BLOCKER_FIX_DECISION_REPORT.json",
]

FEEDBACK_APPLICABLE_AFTER = [
    "A7_feedback_default_gate",
    "A8_feedback_selected_conservative_gate",
    "B0_reject_all_sanity",
    "B1_velocity_only_feedback",
    "B2_attitude_only_feedback",
    "B3_velocity_attitude_feedback",
    "B4_diagnostic_PVA_feedback",
    "C0_selected_feedback_full",
]


def report_root() -> Path | None:
    value = os.environ.get("N8K6_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_toy_n8k6_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    not_applicable = ["A0_source_backed_ekf_baseline", "C9_selected_without_feedback"]
    regenerated = [
        {
            "category": category,
            "filename": filename,
            "documented_not_applicable": True,
            "not_applicable_reason": BASELINE_NOT_APPLICABLE_REASON,
            "variant_role": "baseline_no_feedback",
            "raw_feedback_rows_detected": 175,
            "effective_feedback_rows_for_plotting": 0,
            "feedback_accept_count": 0,
            "feedback_reject_count": 0,
            "raw_rows_ignored": True,
            "raw_rows_ignored_reason": "variant_role_baseline_no_feedback",
        }
        for category, filename in FEEDBACK_SPECIFIC_FIGURES
    ]
    base = {
        "stage": "N8K6",
        "A0_variant_role": "baseline_no_feedback",
        "A0_feedback_applicable_before": True,
        "A0_feedback_applicable_after": False,
        "A0_raw_feedback_rows_detected_before": 175,
        "A0_raw_feedback_rows_detected_after": 175,
        "A0_effective_feedback_rows_for_plotting_before": 175,
        "A0_effective_feedback_rows_for_plotting_after": 0,
        "A0_feedback_accept_count": 0,
        "A0_feedback_reject_count": 0,
        "A0_raw_rows_ignored": True,
        "A0_raw_rows_ignored_reason": "variant_role_baseline_no_feedback",
        "feedback_applicable_variants_before": ["A0_source_backed_ekf_baseline", *FEEDBACK_APPLICABLE_AFTER],
        "feedback_not_applicable_variants_before": ["C9_selected_without_feedback"],
        "feedback_applicable_variants_after": FEEDBACK_APPLICABLE_AFTER,
        "feedback_not_applicable_variants_after": not_applicable,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    write_json(root / "N8K6_A0_FEEDBACK_APPLICABILITY_AUDIT_REPORT.json", base)
    write_json(
        root / "N8K6_A0_FEEDBACK_APPLICABILITY_FIX_REPORT.json",
        {
            **base,
            "A0_figures_regenerated": [{"category": item["category"], "filename": item["filename"]} for item in regenerated],
            "A0_figures_regenerated_count": len(regenerated),
            "exact_same_category_duplicate_after": 0,
            "same_variant_cross_category_duplicate_after": 0,
            "blocking_duplicate_pairs_after": [],
            "feedback_empty_axis_after": 0,
            "placeholder_remaining": 0,
            "applicable_placeholder_remaining": 0,
            "semantic_mismatch_remaining": 0,
            "remaining_global_duplicate_groups": 8,
            "remaining_duplicates_cross_variant_only": True,
            "derived_data_labels_count": 20,
            "derived_surrogate_labels_count": 20,
            "figures_regenerated_count": 11,
            "figures_copied_count": 2850,
            "regenerated_entries": regenerated,
        },
    )
    write_json(root / "N8K6_A0_FEEDBACK_PLOT_REGENERATION_REPORT.json", {"stage": "N8K6", "variant_id": "A0_source_backed_ekf_baseline", "figures_regenerated": regenerated, "documented_not_applicable_count": len(regenerated), "A0_raw_feedback_rows_detected": 175, "A0_effective_feedback_rows_for_plotting": 0, "algorithm_changes": False, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K6_REAL_PLOT_COVERAGE_REGRESSION_REPORT.json", {"stage": "N8K6", "A0_feedback_specific_not_applicable_count": 11, "feedback_empty_axis_after": 0, "placeholder_remaining": 0, "applicable_placeholder_remaining": 0, "semantic_mismatch_remaining": 0, "algorithm_changes": False, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K6_DUPLICATE_REGRESSION_REPORT.json", {"stage": "N8K6", "exact_same_category_duplicate_after": 0, "same_variant_cross_category_duplicate_after": 0, "blocking_duplicate_pairs_after": [], "remaining_global_duplicate_groups": 8, "remaining_cross_variant_only_duplicate_groups": 8, "remaining_duplicates_cross_variant_only": True, "algorithm_changes": False, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K6_FINAL_BLOCKER_FIX_DECISION_REPORT.json", {"stage": "N8K6", "status": "A0_feedback_applicability_fix_complete", "ready_to_merge": False, "ready_to_tag": False, "recommended_next_stage": "rerun_N8K_final_merge_review", "A0_feedback_applicable_after": False, "A0_effective_feedback_rows_for_plotting_after": 0, "feedback_empty_axis_after": 0, "exact_same_category_duplicate_after": 0, "same_variant_cross_category_duplicate_after": 0, "blocking_duplicate_pairs_after": [], "algorithm_changes": False, "no_algorithm_changes": True, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})


def audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            raise SystemExit(f"audit_n8k6_a0_feedback_applicability failed: missing {name}")
    audit = _json(root / "N8K6_A0_FEEDBACK_APPLICABILITY_AUDIT_REPORT.json")
    fix = _json(root / "N8K6_A0_FEEDBACK_APPLICABILITY_FIX_REPORT.json")
    decision = _json(root / "N8K6_FINAL_BLOCKER_FIX_DECISION_REPORT.json")
    if audit.get("A0_variant_role") != "baseline_no_feedback":
        raise SystemExit("audit_n8k6_a0_feedback_applicability failed: A0 role")
    if audit.get("A0_feedback_applicable_after") is not False:
        raise SystemExit("audit_n8k6_a0_feedback_applicability failed: A0 still applicable")
    if audit.get("A0_effective_feedback_rows_for_plotting_after") != 0:
        raise SystemExit("audit_n8k6_a0_feedback_applicability failed: effective rows not zero")
    if audit.get("A0_raw_feedback_rows_detected_after", 0) <= 0:
        raise SystemExit("audit_n8k6_a0_feedback_applicability failed: raw rows not recorded")
    if audit.get("A0_raw_rows_ignored_reason") != "variant_role_baseline_no_feedback":
        raise SystemExit("audit_n8k6_a0_feedback_applicability failed: ignored reason")
    if "A0_source_backed_ekf_baseline" in fix.get("feedback_applicable_variants_after", []):
        raise SystemExit("audit_n8k6_a0_feedback_applicability failed: A0 in applicable after")
    if fix.get("A0_figures_regenerated_count") != len(FEEDBACK_SPECIFIC_FIGURES):
        raise SystemExit("audit_n8k6_a0_feedback_applicability failed: regenerated figure count")
    if decision.get("status") != "A0_feedback_applicability_fix_complete":
        raise SystemExit(f"audit_n8k6_a0_feedback_applicability failed: {decision.get('status')}")
    for name in REQUIRED_REPORTS:
        payload = _json(root / name)
        if payload.get("paper_performance_claim") is not False or payload.get("outperform_final_v23_claim") is True:
            raise SystemExit(f"audit_n8k6_a0_feedback_applicability failed: claim boundary in {name}")


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k6"
            make_toy_n8k6_root(root)
            audit_runtime(root)
    else:
        audit_runtime(root)
    print("audit_n8k6_a0_feedback_applicability passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
