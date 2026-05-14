#!/usr/bin/env python3
"""Audit shortest-angle yaw residual helpers.

中文说明：验证 yaw residual 走 shortest-angle wrap。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_angle_utils import shortest_angle_residual_deg, shortest_angle_residual_rad, wrap_deg, wrap_rad
from legsa_gins.fgo.fgo_yaw_residuals import dual_yaw_residual_deg, yaw_rate_between_residual_deg


def main() -> int:
    if shortest_angle_residual_deg(359.0, 1.0) != -2.0:
        raise SystemExit("359-1 should wrap to -2 deg")
    if shortest_angle_residual_deg(1.0, 359.0) != 2.0:
        raise SystemExit("1-359 should wrap to +2 deg")
    if abs(shortest_angle_residual_rad(-math.pi + 0.01, math.pi - 0.01) - 0.02) > 1e-9:
        raise SystemExit("pi boundary wrap failed")
    for fn in (wrap_deg, wrap_rad):
        try:
            fn(float("nan"))
        except ValueError:
            pass
        else:
            raise SystemExit("NaN should be rejected")
    if dual_yaw_residual_deg(1.0, 359.0) != 2.0:
        raise SystemExit("dual yaw residual wrap failed")
    if yaw_rate_between_residual_deg(359.0, 1.0, 1.0, 1.0) != 1.0:
        raise SystemExit("yaw-rate residual wrap failed")
    print("audit_fgo_yaw_wrap_residuals passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
