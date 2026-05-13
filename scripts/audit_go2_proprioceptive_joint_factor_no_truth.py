#!/usr/bin/env python3
"""Audit N7C6 joint factor keeps Go2 body-state as observation, not truth.

中文说明：确认 Go2 roll/pitch/velocity 只作为本体观测，不作为 truth。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c6_decision import make_n7c6_joint_factor_decision
from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_builder import build_joint_factor_rows


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_proprioceptive_joint_factor_no_truth failed: {message}")


def main() -> int:
    go2_rows = [{"time": 0.0, "aligned_time": 0.0, "roll_rad": 0.01, "pitch_rad": -0.01, "mode": "walk", "gait_type": "trot"}]
    horizontal_rows = [{"time": 0.0, "vn": 1.0, "ve": 0.2, "vd": 0.0}]
    joint_rows, attitude_rows, velocity_rows = build_joint_factor_rows(
        go2_rows=go2_rows,
        horizontal_rows=horizontal_rows,
        std_roll_pitch_deg=1.6,
        std_vn_ve=1.0,
        policy_name="joint_rp1p6deg_hv1p0",
    )
    if not joint_rows or not attitude_rows or not velocity_rows:
        _fail("toy joint rows not built")
    if joint_rows[0].get("go2_truth_claim") != "false":
        _fail("joint row truth claim not false")
    if attitude_rows[0].get("go2_roll_pitch_truth_claim") != "false":
        _fail("attitude truth claim not false")
    if velocity_rows[0].get("go2_velocity_truth_claim") != "false":
        _fail("velocity truth claim not false")
    decision = make_n7c6_joint_factor_decision(
        comparison_report={"comparisons": {}},
        nis_report={"variants": {}},
        figure_manifest={"figure_count_total": 12, "required_figures_generated": True, "required_figures_nonempty": True},
    )
    if not decision.get("go2_not_truth") or decision.get("paper_performance_claim"):
        _fail("decision truth/claim boundary invalid")
    print("audit_go2_proprioceptive_joint_factor_no_truth passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
