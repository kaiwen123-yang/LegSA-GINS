"""N7C5 proprioceptive factor candidate ranking.

中文说明：ranking 只决定哪些 Go2 本体候选值得进入 N7C6/N8A 继续审查，
N7C5 不正式激活新增联合因子。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _score_bool(value: bool, weight: float) -> float:
    return weight if value else 0.0


def _bounded_score(value: float | int | None, good: float, bad: float, weight: float, reverse: bool = False) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return 0.0
    x = float(value)
    if reverse:
        x = max(0.0, min(1.0, (bad - x) / max(1.0e-9, bad - good)))
    else:
        x = max(0.0, min(1.0, (x - bad) / max(1.0e-9, good - bad)))
    return weight * x


def _risk_from_score(score: float) -> str:
    if score >= 75:
        return "low"
    if score >= 55:
        return "medium"
    return "high"


def build_go2_proprioceptive_factor_ranking(
    *,
    inventory_report: dict[str, Any],
    contact_report: dict[str, Any],
    foot_report: dict[str, Any],
    phase_report: dict[str, Any],
    yawrate_report: dict[str, Any],
    relative_report: dict[str, Any],
    n7c4_decision: dict[str, Any],
) -> dict[str, Any]:
    fields = inventory_report.get("fields", {})
    horizontal_ready = n7c4_decision.get("recommended_default_policy") == "fixed_1p0"
    roll_pitch_available = bool(fields.get("rpy", {}).get("available")) and bool(fields.get("quaternion", {}).get("available"))
    contact_weight_ready = bool(contact_report.get("usable_as_weight"))
    foot_score = (
        _score_bool(bool(foot_report.get("candidate_generated")), 20)
        + _bounded_score(foot_report.get("availability_ratio"), 0.60, 0.05, 20)
        + _bounded_score(foot_report.get("rmse_to_receiver"), 0.25, 2.0, 20, reverse=True)
        + _bounded_score(foot_report.get("rmse_to_raw"), 0.25, 2.0, 15, reverse=True)
        + _bounded_score(foot_report.get("slip_risk_mean"), 0.20, 1.0, 15, reverse=True)
        + _score_bool(phase_report.get("factor_gating_ready", False), 10)
    )
    candidates = [
        {
            "factor_id": "go2_horizontal_velocity_fixed_1p0",
            "description": "validated Go2 horizontal velocity factor from N7C4",
            "data_availability": 1.0,
            "frame_clarity": 0.9,
            "physical_plausibility": 0.8,
            "cross_source_consistency": 0.8,
            "ekf_activation_readiness": 1.0 if horizontal_ready else 0.6,
            "fgo_readiness": 0.2,
            "risk_level": "low" if horizontal_ready else "medium",
            "novelty_value": 0.4,
            "score": 86 if horizontal_ready else 66,
        },
        {
            "factor_id": "go2_roll_pitch_strengthened_candidate",
            "description": "roll/pitch proprioceptive attitude factor strength review",
            "data_availability": 1.0 if roll_pitch_available else 0.0,
            "frame_clarity": 0.8,
            "physical_plausibility": 0.75,
            "cross_source_consistency": 0.5,
            "ekf_activation_readiness": 0.55,
            "fgo_readiness": 0.2,
            "risk_level": "medium",
            "novelty_value": 0.35,
            "score": 62 if roll_pitch_available else 20,
        },
        {
            "factor_id": "go2_joint_roll_pitch_horizontal_velocity",
            "description": "joint proprioceptive roll/pitch plus horizontal velocity candidate",
            "data_availability": 1.0 if roll_pitch_available and horizontal_ready else 0.4,
            "frame_clarity": 0.7,
            "physical_plausibility": 0.7,
            "cross_source_consistency": 0.7,
            "ekf_activation_readiness": 0.45,
            "fgo_readiness": 0.25,
            "risk_level": "medium",
            "novelty_value": 0.6,
            "score": 58 if roll_pitch_available and horizontal_ready else 35,
        },
        {
            "factor_id": "foot_kinematic_velocity_candidate",
            "description": "stance-weighted foot kinematic body velocity candidate",
            "data_availability": min(1.0, float(foot_report.get("availability_ratio", 0.0) or 0.0)),
            "frame_clarity": 0.65,
            "physical_plausibility": 1.0 if foot_report.get("physical_plausibility") == "plausible" else 0.45,
            "cross_source_consistency": 0.75 if foot_report.get("activation_candidate") == "ready_for_N7C6" else 0.45,
            "ekf_activation_readiness": 0.85 if foot_report.get("activation_candidate") == "ready_for_N7C6" else 0.25,
            "fgo_readiness": 0.35,
            "risk_level": _risk_from_score(foot_score),
            "novelty_value": 0.85,
            "score": round(foot_score, 3),
        },
        {
            "factor_id": "contact_probability_weighting",
            "description": "probabilistic contact weight/gating source",
            "data_availability": 1.0 if contact_weight_ready else 0.0,
            "frame_clarity": 0.9,
            "physical_plausibility": 0.65,
            "cross_source_consistency": 0.5,
            "ekf_activation_readiness": 0.6 if contact_weight_ready else 0.2,
            "fgo_readiness": 0.4,
            "risk_level": "medium",
            "novelty_value": 0.55,
            "score": 64 if contact_weight_ready else 25,
        },
        {
            "factor_id": "yawrate_between_factor_candidate",
            "description": "Go2 yaw-speed consistency for future between-factor",
            "data_availability": 1.0 if yawrate_report.get("row_count", 0) else 0.0,
            "frame_clarity": 0.7,
            "physical_plausibility": 0.75 if yawrate_report.get("stability_status") == "stable" else 0.4,
            "cross_source_consistency": 0.65 if yawrate_report.get("stability_status") == "stable" else 0.3,
            "ekf_activation_readiness": 0.0,
            "fgo_readiness": 0.7 if yawrate_report.get("stability_status") == "stable" else 0.3,
            "risk_level": "medium",
            "novelty_value": 0.55,
            "score": 61 if yawrate_report.get("stability_status") == "stable" else 36,
        },
        {
            "factor_id": "relative_odometry_between_factor_candidate",
            "description": "Go2 internal position increments as relative odometry candidate",
            "data_availability": 1.0 if relative_report.get("window_count", 0) else 0.0,
            "frame_clarity": 0.45,
            "physical_plausibility": 0.65 if relative_report.get("relative_odometry_stability") == "stable" else 0.35,
            "cross_source_consistency": 0.4,
            "ekf_activation_readiness": 0.0,
            "fgo_readiness": 0.7 if relative_report.get("relative_odometry_stability") == "stable" else 0.25,
            "risk_level": "medium",
            "novelty_value": 0.7,
            "score": 55 if relative_report.get("relative_odometry_stability") == "stable" else 31,
        },
    ]
    ranked = sorted(candidates, key=lambda row: float(row["score"]), reverse=True)
    ekf_ready = [row["factor_id"] for row in ranked if row["factor_id"] in {"go2_horizontal_velocity_fixed_1p0", "foot_kinematic_velocity_candidate"} and row["score"] >= 70]
    fgo_candidates = [row["factor_id"] for row in ranked if row.get("fgo_readiness", 0.0) >= 0.65]
    return {
        "stage": "N7C5_go2_full_proprioceptive_factor_mining",
        "candidates": ranked,
        "recommended_EKF_next_factor": ekf_ready[0] if ekf_ready else "none",
        "recommended_FGO_candidate_factors": fgo_candidates,
        "factors_not_ready": [row["factor_id"] for row in ranked if row["score"] < 55],
        "reason": "N7C5 ranks candidates for N7C6/N8A; it does not formally activate new Go2 fields",
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_go2_proprioceptive_factor_ranking(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
