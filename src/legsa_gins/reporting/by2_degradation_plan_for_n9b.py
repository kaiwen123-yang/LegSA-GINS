"""N8K placeholder plan for N9B degradation matrix."""

# 中文说明：这里只生成 N9B 退化实验计划，不运行退化矩阵。

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


def build_n9b_degradation_plan() -> dict[str, Any]:
    return {
        "stage": "N8K",
        "plan_only": True,
        "degradation_matrix_run": False,
        "recommended_stage": "N9B_BY2_full_degradation_matrix",
        "n9b_existing_degradations": ["outage", "sampling", "position_noise", "position_spike", "std_inflation", "yaw_spike", "yawstd_inflation"],
        "n9b_extended_degradations": [
            "receiver_velocity_degradation",
            "raw_doppler_degradation",
            "go2_attitude_degradation",
            "go2_horizontal_velocity_degradation",
            "contact_probability_degradation",
            "foot_kinematic_degradation",
            "yaw_rate_and_relative_odometry_degradation",
            "combined_degradation",
        ],
        "n9c": "degradation figures and case review",
        "n9d": "math/output-evaluation/filter-construction full-chain audit",
        "no_degradation_runtime_outputs_generated": True,
        "paper_performance_claim": False,
    }


def write_n9b_degradation_plan(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
