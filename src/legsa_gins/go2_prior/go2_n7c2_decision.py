"""Decision rules for N7C2 visual readability and Jacobian audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7c2_decision(
    *,
    overlap_report: dict[str, Any],
    figure_manifest: dict[str, Any],
    jacobian_report: dict[str, Any],
) -> dict[str, Any]:
    """Map N7C2 evidence to the PR #38 merge-readiness recommendation.

    中文说明：N7C2 只决定是否存在图像/Jacobian blocker；不 merge PR、不 tag、
    不进入 N8A 实现。
    """

    go2_boundary_ok = bool(
        jacobian_report.get("go2_horizontal_touches_only_horizontal_velocity")
        and jacobian_report.get("go2_horizontal_vertical_derivative_zero")
        and not jacobian_report.get("go2_horizontal_position_prior_enabled", True)
        and not jacobian_report.get("go2_horizontal_yaw_prior_enabled", True)
        and not jacobian_report.get("go2_vertical_velocity_prior_enabled", True)
    )
    if not figure_manifest.get("required_figures_generated") or not figure_manifest.get("required_figures_nonempty"):
        status = "visual_readability_not_ready"
        next_stage = "N7C2_visual_readability_repair"
    elif not jacobian_report.get("all_active_factor_contracts_present"):
        status = "jacobian_contract_not_ready"
        next_stage = "N7C2_factor_contract_repair"
    elif not go2_boundary_ok:
        status = "go2_horizontal_jacobian_boundary_failed"
        next_stage = "N7C2_go2_horizontal_boundary_fix"
    else:
        status = "ready_to_merge_N7C_and_start_N8A"
        next_stage = "merge_PR_38_tag_N7C_then_start_N8A"
    return {
        "stage": "N7C2_go2_horizontal_velocity_jacobian_visual_audit",
        "status": status,
        "recommended_next_stage": next_stage,
        "visual_overlap_explained": bool(overlap_report.get("summary", {}).get("all_overlaps_explained")),
        "readability_figures_generated": bool(figure_manifest.get("required_figures_generated")),
        "readability_figures_nonempty": bool(figure_manifest.get("required_figures_nonempty")),
        "factor_jacobian_contract_status": "passed" if jacobian_report.get("all_active_factor_contracts_present") and go2_boundary_ok else "failed",
        "go2_horizontal_H_nonzero_blocks": jacobian_report.get("go2_horizontal_H_nonzero_blocks", []),
        "go2_horizontal_vertical_derivative_zero": bool(jacobian_report.get("go2_horizontal_vertical_derivative_zero")),
        "toy_finite_difference_status": jacobian_report.get("toy_finite_difference_status"),
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_vertical_velocity_prior_enabled": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }


def write_n7c2_decision(path: str | Path, report: dict[str, Any]) -> dict[str, Any]:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
