#!/usr/bin/env python3
"""Audit N8A1 yaw convention logic on a wrap-boundary toy case.

中文说明：toy 审计验证 0/360 环绕异常会被识别为 blocker。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_yaw_convention_audit import audit_yaw_convention


def main() -> int:
    ekf_rows = [
        {"time": 0.0, "yaw_deg": 359.0},
        {"time": 1.0, "yaw_deg": 1.0},
        {"time": 2.0, "yaw_deg": 2.0},
    ]
    fgo_rows = [
        {"time": 0.0, "yaw_deg": 180.0},
        {"time": 1.0, "yaw_deg": 120.0},
        {"time": 2.0, "yaw_deg": 2.0},
    ]
    report = audit_yaw_convention(ekf_rows=ekf_rows, fgo_rows=fgo_rows)
    if report.get("blocker_status") != "yaw_wrap_residual_blocker":
        raise SystemExit(f"expected yaw wrap blocker, got {report.get('blocker_status')}")
    if report.get("trace_solver_input") or report.get("final_v23_output_solver_input"):
        raise SystemExit("forbidden solver input flag set")
    print("audit_fgo_yaw_convention passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
