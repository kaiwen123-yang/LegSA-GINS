"""N8A factor registry and boundary contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_types import FGOFactorContract


def build_default_factor_registry() -> dict[str, Any]:
    """中文说明：active/default 和 diagnostic candidate factor 边界集中登记。"""
    factors = [
        FGOFactorContract("ReceiverPositionFactor", "receiver", True, False, 3, ("position",), "receiver_position", "receiver_position_covariance"),
        FGOFactorContract("ReceiverVelocityFactor", "receiver", True, False, 3, ("velocity",), "receiver_velocity", "receiver_velocity_covariance"),
        FGOFactorContract(
            "DualYawFactor",
            "dual_antenna",
            True,
            False,
            1,
            ("yaw",),
            "dual_antenna_yaw",
            "dual_yaw_std",
            residual_formula="wrap(yaw_state - yaw_measurement)",
        ),
        FGOFactorContract("RawDopplerVelocityFactor", "rtklib_doppler", True, False, 3, ("velocity",), "raw_doppler_velocity", "raw_doppler_covariance"),
        FGOFactorContract(
            "Go2ProprioceptiveJointFactor",
            "go2_body_state",
            True,
            False,
            4,
            ("attitude_roll", "attitude_pitch", "velocity_north", "velocity_east"),
            "go2_roll_pitch_horizontal_velocity",
            "diag(std_roll^2,std_pitch^2,std_vn^2,std_ve^2)",
        ),
        FGOFactorContract(
            "SmoothnessFactor",
            "temporal_model",
            True,
            False,
            9,
            ("position", "attitude", "velocity"),
            "neighbor_state",
            "fixed_temporal_smoothness",
            residual_formula="yaw component uses wrap((yaw_next - yaw_prev) - expected_delta_yaw)",
        ),
        FGOFactorContract("Go2FootKinematicVelocityFactor", "go2_foot_kinematics", False, True, 2, ("velocity_north", "velocity_east"), "foot_kinematic_velocity_candidate", "diagnostic_candidate_covariance"),
        FGOFactorContract(
            "Go2YawRateBetweenFactor",
            "go2_yawrate",
            False,
            True,
            1,
            ("yaw",),
            "go2_yawrate_candidate",
            "diagnostic_between_factor_covariance",
            residual_formula="wrap((yaw_next - yaw_prev) - yaw_rate * dt)",
        ),
        FGOFactorContract("Go2RelativeOdometryBetweenFactor", "go2_position_increment", False, True, 3, ("position",), "go2_relative_odometry_candidate", "diagnostic_between_factor_covariance"),
        FGOFactorContract("ContactProbabilityWeightingFactor", "go2_contact_probability", False, True, 0, tuple(), "contact_probability_weight", "weighting_only_not_hard_prior"),
    ]
    factor_dicts = [factor.to_dict() for factor in factors]
    return {
        "stage": "N8A_no_feedback_fgo_foundation",
        "factors": factor_dicts,
        "active_default_factors": [row["factor_name"] for row in factor_dicts if row["active_default"]],
        "diagnostic_candidate_factors": [row["factor_name"] for row in factor_dicts if row["diagnostic_only"]],
        "go2_joint_factor_contract": {
            "residual": "[roll_state-roll_go2, pitch_state-pitch_go2, vN_state-vN_go2, vE_state-vE_go2]",
            "touches": ["attitude_roll", "attitude_pitch", "velocity_north", "velocity_east"],
            "no_yaw": True,
            "no_position": True,
            "no_vertical_velocity": True,
            "go2_not_truth": True,
        },
        "forbidden_default_factors": ["Go2AbsolutePositionFactor", "Go2AbsoluteYawFactor", "Go2VerticalVelocityFactor", "Go2ContactHardPrior"],
        "no_feedback": True,
        "fgo_output_replaces_ekf_nav": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_factor_registry_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
