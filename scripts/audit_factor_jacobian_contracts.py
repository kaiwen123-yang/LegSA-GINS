#!/usr/bin/env python3
"""Audit N7C2 factor Jacobian contract report.

中文说明：该审计检查 factor contract 和 toy finite-difference，不修改滤波器。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_factor_jacobian_contract import build_go2_factor_jacobian_contract_report


REQUIRED_FACTORS = {
    "receiver_position",
    "receiver_velocity",
    "dual_antenna_yaw",
    "raw_doppler_velocity",
    "source_aware_scaling",
    "go2_attitude_roll_pitch_weak_prior",
    "go2_horizontal_velocity_weak_prior",
}


def _fail(message: str) -> None:
    raise SystemExit(f"audit_factor_jacobian_contracts failed: {message}")


def main() -> int:
    report = build_go2_factor_jacobian_contract_report()
    names = set(report.get("factor_names", []))
    missing = sorted(REQUIRED_FACTORS - names)
    if missing:
        _fail("missing factor contracts: " + ", ".join(missing))
    if not report.get("all_active_factor_contracts_present"):
        _fail("all_active_factor_contracts_present is false")
    if report.get("toy_finite_difference_status") != "toy_passed":
        _fail("toy finite-difference status is not toy_passed")
    if report.get("go2_horizontal_H_nonzero_blocks") != ["velocity_north", "velocity_east"]:
        _fail("Go2 horizontal H nonzero blocks are not vn/ve only")
    if not report.get("go2_horizontal_vertical_derivative_zero"):
        _fail("Go2 horizontal vertical derivative is not zero")
    if report.get("go2_horizontal_position_prior_enabled") or report.get("go2_horizontal_yaw_prior_enabled"):
        _fail("Go2 horizontal contract enabled position/yaw prior")
    if report.get("go2_vertical_velocity_prior_enabled"):
        _fail("Go2 vertical velocity prior enabled")
    if report.get("trace_solver_input") or report.get("final_v23_output_solver_input"):
        _fail("forbidden solver input flag true")
    if report.get("paper_performance_claim") or report.get("go2_velocity_truth_claim"):
        _fail("forbidden claim flag true")
    print("audit_factor_jacobian_contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
