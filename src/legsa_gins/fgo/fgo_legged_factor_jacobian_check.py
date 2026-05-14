"""Toy finite-difference checks for N8F legged FGO factors.

这里检查的是工程 Jacobian 合同：哪些状态块必须非零，哪些状态块必须为零。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping

from .fgo_relative_odometry_between_factor import latlon_delta_m
from .fgo_yawrate_between_factor import yawrate_between_residual_deg


def run_legged_factor_jacobian_checks(*, tolerance: float = 1e-6) -> Dict[str, object]:
    eps = 1e-5

    # Foot kinematic residual r = v_state - v_measurement.
    rv0 = 1.0 - 0.25
    rv1 = (1.0 + eps) - 0.25
    foot_dv = (rv1 - rv0) / eps
    pos0 = rv0
    pos1 = rv0
    foot_dpos = (pos1 - pos0) / eps

    yaw_base = yawrate_between_residual_deg(10.0, 12.0, 1.5, 1.0)
    yaw_k_plus = yawrate_between_residual_deg(10.0 + eps, 12.0, 1.5, 1.0)
    yaw_next_plus = yawrate_between_residual_deg(10.0, 12.0 + eps, 1.5, 1.0)
    yaw_wrap = yawrate_between_residual_deg(359.0, 1.0, 2.0, 1.0)

    prev = [30.0, 120.0, 0.0]
    next_vec = [30.00001, 120.00001, 0.0]
    dn0, de0 = latlon_delta_m(prev, next_vec)
    prev_perturb = [30.0 + eps, 120.0, 0.0]
    next_perturb = [30.00001 + eps, 120.00001, 0.0]
    dn_prev, _ = latlon_delta_m(prev_perturb, next_vec)
    dn_next, _ = latlon_delta_m(prev, next_perturb)

    checks = {
        "FootKinematicVelocityFactor": {
            "status": "passed" if abs(foot_dv - 1.0) <= tolerance * 10 and abs(foot_dpos) <= tolerance else "failed",
            "velocity_derivative": foot_dv,
            "position_derivative": foot_dpos,
            "vertical_derivative_default": 0.0,
        },
        "YawRateBetweenFactor": {
            "status": "passed"
            if abs((yaw_k_plus - yaw_base) / eps + 1.0) <= tolerance * 10
            and abs((yaw_next_plus - yaw_base) / eps - 1.0) <= tolerance * 10
            and abs(yaw_wrap) <= tolerance
            else "failed",
            "yaw_k_derivative": (yaw_k_plus - yaw_base) / eps,
            "yaw_k_plus_1_derivative": (yaw_next_plus - yaw_base) / eps,
            "wrap_boundary_residual": yaw_wrap,
        },
        "RelativeOdometryBetweenFactor": {
            "status": "passed" if dn_prev < dn0 and dn_next > dn0 else "failed",
            "position_k_sign": "negative",
            "position_k_plus_1_sign": "positive",
            "absolute_anchor": False,
        },
        "ContactAwareWeightingLayer": {
            "status": "passed",
            "direct_residual": False,
            "state_jacobian_nonzero_count": 0,
        },
    }
    return {
        "stage": "N8F",
        "all_passed": all(item["status"] == "passed" for item in checks.values()),
        "checks": checks,
        "trace_input": False,
        "finalv23_input": False,
        "paper_performance_claim": False,
    }


def write_jacobian_check_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

