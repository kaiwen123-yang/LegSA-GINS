"""Decision rules for N8A no-feedback FGO foundation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n8a_decision(*, backend: dict[str, Any], registry: dict[str, Any], dataset: dict[str, Any], smoother: dict[str, Any], evaluation: dict[str, Any], figures: dict[str, Any]) -> dict[str, Any]:
    """中文说明：N8A ready 只说明 foundation 可运行，不是性能 claim。"""
    blockers: list[str] = []
    if dataset.get("state_count", 0) <= 0:
        blockers.append("no_state_nodes")
    if smoother.get("solve_status") != "solved":
        blockers.append("fgo_solve_failed")
    if not figures.get("required_figures_generated") or not figures.get("required_figures_nonempty"):
        blockers.append("figures_missing")
    if not registry.get("no_feedback") or smoother.get("fgo_output_feedback_to_ekf"):
        blockers.append("feedback_boundary_failed")
    status = "n8a_no_feedback_fgo_foundation_ready" if not blockers else "n8a_foundation_not_ready"
    return {
        "stage": "N8A_no_feedback_fgo_foundation",
        "status": status,
        "recommended_next_stage": "N8B_factor_graph_policy_review" if not blockers else "N8A_fix_foundation",
        "blocker_reasons": blockers,
        "backend_selected": backend.get("selected_backend"),
        "state_count": dataset.get("state_count", 0),
        "active_factor_count_estimate": dataset.get("active_factor_count_estimate", 0),
        "diagnostic_candidate_factor_count_estimate": dataset.get("diagnostic_candidate_factor_count_estimate", 0),
        "solve_status": smoother.get("solve_status"),
        "evaluation_metric_namespace": evaluation.get("metric_namespace"),
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "paper_performance_claim": False,
    }


def write_decision(path: str | Path, decision: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
