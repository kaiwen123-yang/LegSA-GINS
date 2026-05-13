"""N7C5A visual review decision.

中文说明：若 N7C5 图像复核无 blocker，才允许进入 N7C6 joint observation factor。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7c5a_visual_decision(
    *,
    sanity_report: dict[str, Any],
    coverage_report: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> dict[str, Any]:
    blocker = bool(sanity_report.get("visual_blocker"))
    status = "n7c5_visual_blocker" if blocker else "n7c5_visual_review_passed"
    next_stage = "N7C5B_fix_visual_or_candidate_data" if blocker else "N7C6_go2_proprioceptive_joint_factor"
    return {
        "stage": "N7C5A_go2_full_proprioceptive_visual_review",
        "status": status,
        "recommended_next_stage": next_stage,
        "visual_blocker": blocker,
        "blocker_reasons": sanity_report.get("blocker_reasons", []),
        "figure_count": figure_manifest.get("figure_count_total", 0),
        "required_figures_generated": bool(figure_manifest.get("required_figures_generated")),
        "required_figures_nonempty": bool(figure_manifest.get("required_figures_nonempty")),
        "contact_rows_summary_only": bool(coverage_report.get("contact_rows_summary_only")),
        "go2_not_truth": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_n7c5a_visual_decision(path: str | Path, decision: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
