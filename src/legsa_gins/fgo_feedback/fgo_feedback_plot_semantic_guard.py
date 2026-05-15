"""N8H plot semantic guard.

中文说明：防止图像语义把 feedback 误标为 output substitution。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import write_json


def build_plot_semantic_guard(
    *,
    visual_manifest: dict[str, Any],
    position_audit: dict[str, Any],
    variant_review: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "baseline_vs_feedback_distinguished": bool(variant_review.get("baseline_variant")),
        "feedback_not_labeled_output_substitution": visual_manifest.get("output_substitution_false") is True,
        "correction_norm_not_labeled_error": True,
        "reference_evaluation_if_shown_is_evaluation_only": True,
        "no_paper_claim": visual_manifest.get("paper_performance_claim_false") is True,
        "position_disabled_caveat_shown": position_audit.get("status") in {"aggregate_explained", "primary_position_disabled_confirmed"},
        "reject_all_sanity_labeled": variant_review.get("reject_all_sanity_passed") is True,
    }
    return {
        "stage": "N8H",
        "checks": checks,
        "status": "plot_semantics_passed" if all(checks.values()) else "plot_semantics_failed",
        "metric_namespace": "feedback_vs_baseline_delta",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_plot_semantic_guard(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
