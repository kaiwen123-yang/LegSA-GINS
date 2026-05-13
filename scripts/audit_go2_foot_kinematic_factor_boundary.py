#!/usr/bin/env python3
"""Audit N7C5 foot kinematic candidate boundary.

中文说明：本审计检查 foot kinematic velocity 只是候选诊断，不启用 Go2
position/yaw/vertical velocity prior，不声称 Go2/foot/contact 为 truth。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_foot_kinematic_velocity_candidate import build_go2_foot_kinematic_velocity_candidate
from legsa_gins.go2_prior.go2_n7c5_decision import make_n7c5_decision


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_foot_kinematic_factor_boundary failed: {message}")


def main() -> int:
    go2 = [
        {
            "time": 0.0,
            "aligned_time": 0.0,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
            "roll_rad": 0.0,
            "pitch_rad": 0.0,
            "yaw_rad": 0.0,
            **{f"foot_position_body_{3 * foot + axis}": value for foot in range(4) for axis, value in enumerate([0.2, 0.1, -0.3])},
            **{f"foot_speed_body_{3 * foot + axis}": value for foot in range(4) for axis, value in enumerate([-1.0, -0.2, 0.0])},
        }
    ]
    contact = [{"time": 0.0, **{f"foot_{foot}_contact_probability": 0.9 for foot in range(4)}}]
    velocity = [{"time": 0.0, "vn": 1.0, "ve": 0.2, "vd": 0.0}]
    rows, report = build_go2_foot_kinematic_velocity_candidate(
        go2_rows=go2,
        contact_rows=contact,
        go2_velocity_rows=velocity,
        receiver_velocity_rows=velocity,
        raw_doppler_rows=velocity,
    )
    if not rows:
        _fail("candidate rows missing")
    if not math.isclose(float(rows[0]["candidate_vn"]), 1.0, abs_tol=1.0e-9):
        _fail("candidate vn formula mismatch")
    if report.get("not_truth") is not True or report.get("paper_performance_claim") is not False:
        _fail("foot report boundary flags invalid")
    decision = make_n7c5_decision(
        foot_report=report,
        yawrate_report={"stability_status": "diagnostic_only"},
        relative_report={"relative_odometry_stability": "diagnostic_only"},
        ranking_report={"recommended_EKF_next_factor": "foot_kinematic_velocity_candidate", "recommended_FGO_candidate_factors": []},
        n7c4_decision={"recommended_default_policy": "fixed_1p0"},
        figure_manifest={"figure_count_total": 10, "required_figures_generated": True, "required_figures_nonempty": True},
    )
    if decision.get("formal_activation_in_n7c5"):
        _fail("N7C5 decision formally activates foot kinematic factor")
    if decision.get("go2_position_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("go2_vertical_velocity_prior_enabled"):
        _fail("forbidden Go2 prior enabled")
    print("audit_go2_foot_kinematic_factor_boundary passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
