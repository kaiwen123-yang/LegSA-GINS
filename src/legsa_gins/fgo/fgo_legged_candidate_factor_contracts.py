"""N8F legged candidate factor contracts.

合同报告把每个正式激活的候选因子声明为 residual/Jacobian/边界三元组。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping


def build_legged_candidate_factor_contracts(
    *,
    contact_report: Mapping[str, object],
    foot_report: Mapping[str, object],
    yawrate_report: Mapping[str, object],
    relative_report: Mapping[str, object],
    jacobian_report: Mapping[str, object],
) -> Dict[str, object]:
    checks = jacobian_report.get("checks", {}) if isinstance(jacobian_report.get("checks"), Mapping) else {}
    contracts = [
        {
            "factor_name": "ContactAwareWeightingLayer",
            "residual_dimension": 0,
            "state_blocks_touched": [],
            "measurement_source": "N7C5 contact probability / support probability / slip risk",
            "R_policy": "R scale only; high support lowers scale, high slip or uncertainty raises scale",
            "contact_aware_scaling": True,
            "no_truth_claim": True,
            "trace_input": False,
            "finalv23_input": False,
            "jacobian_toy_check_status": checks.get("ContactAwareWeightingLayer", {}).get("status", "missing"),
            "factor_rows": contact_report.get("rows", 0),
        },
        {
            "factor_name": "FootKinematicVelocityFactor",
            "residual_dimension": 2,
            "state_blocks_touched": ["velocity_north", "velocity_east"],
            "measurement_source": foot_report.get("measurement_source", "N7C5_foot_kinematic_velocity_candidate"),
            "R_policy": "conservative floor plus contact-aware R scaling",
            "contact_aware_scaling": True,
            "no_truth_claim": not bool(foot_report.get("go2_truth_claim", True)),
            "trace_input": False,
            "finalv23_input": False,
            "jacobian_toy_check_status": checks.get("FootKinematicVelocityFactor", {}).get("status", "missing"),
            "factor_rows": foot_report.get("factor_rows", 0),
        },
        {
            "factor_name": "YawRateBetweenFactor",
            "residual_dimension": 1,
            "state_blocks_touched": ["yaw_k", "yaw_k_plus_1"],
            "measurement_source": yawrate_report.get("measurement_source", "N7C5_go2_yaw_speed_candidate"),
            "R_policy": "conservative yaw-rate consistency scale",
            "contact_aware_scaling": False,
            "no_truth_claim": not bool(yawrate_report.get("absolute_yaw_truth_claim", True)),
            "trace_input": False,
            "finalv23_input": False,
            "jacobian_toy_check_status": checks.get("YawRateBetweenFactor", {}).get("status", "missing"),
            "factor_rows": yawrate_report.get("factor_rows", 0),
        },
        {
            "factor_name": "RelativeOdometryBetweenFactor",
            "residual_dimension": 2,
            "state_blocks_touched": ["position_k", "position_k_plus_1"],
            "measurement_source": relative_report.get("measurement_source", "N7C5_go2_relative_odometry_increment_candidate"),
            "R_policy": "conservative short-window scale with optional contact-aware scaling",
            "contact_aware_scaling": True,
            "no_truth_claim": not bool(relative_report.get("go2_position_truth_claim", True)),
            "trace_input": False,
            "finalv23_input": False,
            "jacobian_toy_check_status": checks.get("RelativeOdometryBetweenFactor", {}).get("status", "missing"),
            "factor_rows": relative_report.get("factor_rows", 0),
        },
    ]
    return {
        "stage": "N8F",
        "contracts": contracts,
        "all_jacobian_checks_passed": bool(jacobian_report.get("all_passed", False)),
        "all_no_truth_claim": all(bool(row["no_truth_claim"]) for row in contracts),
        "all_trace_input_false": all(not bool(row["trace_input"]) for row in contracts),
        "all_finalv23_input_false": all(not bool(row["finalv23_input"]) for row in contracts),
        "no_feedback": True,
        "no_output_substitution": True,
        "paper_performance_claim": False,
    }


def write_contracts_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

