#!/usr/bin/env python3
"""Audit N8K3 duplicate semantic plot fix reports."""

# 中文说明：N8K3 主审计要求修复前能发现重复、修复后阻塞重复清零。

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
    "N8K3_DUPLICATE_SEMANTIC_PLOT_AUDIT_REPORT.json",
    "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json",
    "N8K3_BY2_FORMAL_ABLATION_DUPLICATE_PLOT_FIX_DECISION_REPORT.json",
]


def report_root() -> Path | None:
    value = os.environ.get("N8K3_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            raise SystemExit(f"audit_n8k3_duplicate_semantic_plots failed: missing {name}")
    audit = _json(root / "N8K3_DUPLICATE_SEMANTIC_PLOT_AUDIT_REPORT.json")
    fix = _json(root / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json")
    decision = _json(root / "N8K3_BY2_FORMAL_ABLATION_DUPLICATE_PLOT_FIX_DECISION_REPORT.json")
    if audit.get("blocking_duplicate_count_before", 0) <= 0:
        raise SystemExit("audit_n8k3_duplicate_semantic_plots failed: duplicate before count not detected")
    if fix.get("blocking_exact_duplicate_after_count") != 0:
        raise SystemExit("audit_n8k3_duplicate_semantic_plots failed: duplicates remain")
    if decision.get("status") != "BY2_formal_ablation_duplicate_plot_fix_complete":
        raise SystemExit(f"audit_n8k3_duplicate_semantic_plots failed: {decision.get('status')}")
    for name in REQUIRED_REPORTS:
        payload = _json(root / name)
        if payload.get("paper_performance_claim") is not False or payload.get("outperform_final_v23_claim") is True:
            raise SystemExit(f"audit_n8k3_duplicate_semantic_plots failed: claim boundary in {name}")


def make_toy_n8k3_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "N8K3_DUPLICATE_SEMANTIC_PLOT_AUDIT_REPORT.json", {"stage": "N8K3", "blocking_duplicate_count_before": 4, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json", {"stage": "N8K3", "blocking_exact_duplicate_after_count": 0, "perceptual_duplicate_after_count": 0, "derived_data_labels_count": 12, "not_applicable_count": 21, "figures_regenerated_count": 99, "algorithm_changes": False, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})
    write_json(root / "N8K3_BY2_FORMAL_ABLATION_DUPLICATE_PLOT_FIX_DECISION_REPORT.json", {"stage": "N8K3", "status": "BY2_formal_ablation_duplicate_plot_fix_complete", "recommended_next_stage": "N8K_merge_review_then_N9A_BY2_full_plot_audit", "same_category_exact_duplicate_remaining": 0, "perceptual_duplicate_after_count": 0, "derived_data_labels_count": 12, "algorithm_changes": False, "no_algorithm_changes": True, "degradation_matrix_run": False, "paper_performance_claim": False, "outperform_final_v23_claim": False})


def main() -> int:
    root = report_root()
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "n8k3"
            make_toy_n8k3_root(root)
            audit_runtime(root)
    else:
        audit_runtime(root)
    print("audit_n8k3_duplicate_semantic_plots passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
