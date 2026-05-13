"""N7C5 decision rules for Go2 full proprioceptive factor mining.

中文说明：N7C5 只选择候选进入下一阶段；除既有 validated factors 外，
不正式激活新的 Go2 EKF/FGO 因子。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_n7c5_decision(
    *,
    foot_report: dict[str, Any],
    yawrate_report: dict[str, Any],
    relative_report: dict[str, Any],
    ranking_report: dict[str, Any],
    n7c4_decision: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> dict[str, Any]:
    foot_ready = foot_report.get("activation_candidate") == "ready_for_N7C6"
    horizontal_attitude_stable = n7c4_decision.get("recommended_default_policy") == "fixed_1p0"
    yaw_stable = yawrate_report.get("stability_status") == "stable"
    rel_stable = relative_report.get("relative_odometry_stability") == "stable"
    if foot_ready:
        status = "ready_for_N7C6_foot_kinematic_velocity_factor"
        next_stage = "N7C6_foot_kinematic_velocity_factor_activation"
    elif horizontal_attitude_stable:
        status = "go2_horizontal_velocity_and_attitude_factor_sufficient"
        next_stage = "N8A_no_feedback_FGO_foundation"
    else:
        status = "no_more_go2_ekf_factors_ready"
        next_stage = "N8A_no_feedback_FGO_foundation"
    return {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "status": status,
        "recommended_next_stage": next_stage,
        "secondary_recommendation": "N8A_yawrate_between_factor_candidate" if yaw_stable else "none",
        "fgo_candidate": "go2_relative_odometry_between_factor" if rel_stable else "none",
        "recommended_EKF_next_factor": ranking_report.get("recommended_EKF_next_factor"),
        "recommended_FGO_candidate_factors": ranking_report.get("recommended_FGO_candidate_factors", []),
        "foot_kinematic_activation_candidate": foot_report.get("activation_candidate"),
        "foot_kinematic_physical_plausibility": foot_report.get("physical_plausibility"),
        "yawrate_stability_status": yawrate_report.get("stability_status"),
        "relative_odometry_stability": relative_report.get("relative_odometry_stability"),
        "figure_count": figure_manifest.get("figure_count_total", 0),
        "figures_generated": bool(figure_manifest.get("required_figures_generated", False)),
        "figures_nonempty": bool(figure_manifest.get("required_figures_nonempty", False)),
        "formal_activation_in_n7c5": False,
        "paper_performance_claim": False,
        "go2_not_truth": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "output_only_correction": False,
        "fgo": False,
    }


def write_n7c5_decision(path: str | Path, decision: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
