#!/usr/bin/env python3
"""Audit N7C6 joint factor Jacobian boundary and toy finite difference.

中文说明：检查 joint factor 只触碰 roll/pitch 和水平速度状态块。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_jacobian import build_joint_factor_jacobian_contract


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_proprioceptive_joint_factor_jacobian failed: {message}")


def main() -> int:
    report = build_joint_factor_jacobian_contract()
    if report.get("finite_difference_check_status") != "toy_passed":
        _fail("toy finite difference did not pass")
    nonzero = set(report.get("nonzero_state_blocks", []))
    expected = {"attitude_roll", "attitude_pitch", "velocity_north", "velocity_east"}
    if nonzero != expected:
        _fail(f"unexpected nonzero blocks {sorted(nonzero)}")
    zero_blocks = set(report.get("zero_state_blocks", []))
    for forbidden in ["position", "velocity_down", "attitude_yaw"]:
        if forbidden not in zero_blocks:
            _fail(f"missing zero-state block {forbidden}")
    if not report.get("vertical_velocity_disabled"):
        _fail("vertical velocity not disabled")
    print("audit_go2_proprioceptive_joint_factor_jacobian passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
