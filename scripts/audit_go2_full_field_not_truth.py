#!/usr/bin/env python3
"""Audit N7C5 Go2 full-field reports keep not-truth boundaries.

中文说明：本审计从 toy report 检查 Go2 position/velocity/contact/roll/pitch
都不是 truth，并且 Go2 position/yaw/vertical velocity prior 仍为 disabled。
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_contact_probability_factor_review import build_go2_contact_probability_factor_review
from legsa_gins.go2_prior.go2_full_field_inventory import build_go2_full_field_inventory
from legsa_gins.go2_prior.go2_n7c5_decision import make_n7c5_decision


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_full_field_not_truth failed: {message}")


def main() -> int:
    row = {
        "time": 0.0,
        "aligned_time": 0.0,
        "quat_w": 1.0,
        "quat_x": 0.0,
        "quat_y": 0.0,
        "quat_z": 0.0,
        "roll_rad": 0.0,
        "pitch_rad": 0.0,
        "yaw_rad": 0.0,
        "gyro_x": 0.0,
        "gyro_y": 0.0,
        "gyro_z": 0.0,
        "acc_x": 0.0,
        "acc_y": 0.0,
        "acc_z": 9.8,
        "mode": 1,
        "gait_type": 2,
        "body_height": 0.32,
        "yaw_speed_radps": 0.0,
        **{f"go2_position_{axis}": 0.0 for axis in range(3)},
        **{f"go2_velocity_{axis}": 0.0 for axis in range(3)},
        **{f"foot_force_{foot}": 70.0 for foot in range(4)},
        **{f"foot_position_body_{idx}": 0.1 for idx in range(12)},
        **{f"foot_speed_body_{idx}": 0.0 for idx in range(12)},
    }
    inventory = build_go2_full_field_inventory([row])
    contact = build_go2_contact_probability_factor_review(
        [{"time": 0.0, **{f"foot_{foot}_contact_probability": 0.8 for foot in range(4)}, "support_probability": 0.8, "swing_probability": 0.2, "uncertainty_probability": 0.1, "alternating_contact_hint": 0.8, "hard_contact_count": 4}]
    )
    decision = make_n7c5_decision(
        foot_report={"activation_candidate": "diagnostic_only", "physical_plausibility": "needs_more_evidence"},
        yawrate_report={"stability_status": "diagnostic_only"},
        relative_report={"relative_odometry_stability": "diagnostic_only"},
        ranking_report={"recommended_EKF_next_factor": "go2_horizontal_velocity_fixed_1p0", "recommended_FGO_candidate_factors": []},
        n7c4_decision={"recommended_default_policy": "fixed_1p0"},
        figure_manifest={"figure_count_total": 10, "required_figures_generated": True, "required_figures_nonempty": True},
    )
    if not inventory.get("not_truth") or inventory.get("go2_velocity_truth_claim") or inventory.get("go2_position_truth_claim"):
        _fail("inventory truth flags invalid")
    if contact.get("contact_truth_claim"):
        _fail("contact truth claim enabled")
    if not decision.get("go2_not_truth"):
        _fail("decision missing Go2 not-truth flag")
    if decision.get("go2_position_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("go2_vertical_velocity_prior_enabled"):
        _fail("forbidden prior enabled in decision")
    print("audit_go2_full_field_not_truth passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
