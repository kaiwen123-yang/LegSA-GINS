#!/usr/bin/env python3
"""Audit yaw smoothness residual wrapping.

中文说明：验证 smoothness yaw residual 不跨 0/360 产生大跳变。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_yaw_smoothness_factor_fix import smooth_yaw_series_deg, yaw_smoothness_residual_series


def main() -> int:
    residuals = yaw_smoothness_residual_series([359.0, 1.0, 2.0])
    if residuals[0] != 2.0:
        raise SystemExit(f"expected +2 deg smoothness residual, got {residuals[0]}")
    if any(abs(value) > 10.0 for value in residuals):
        raise SystemExit("smoothness residual spike detected")
    smoothed = smooth_yaw_series_deg([359.0, 1.0, 2.0])
    if any(90.0 < value < 270.0 for value in smoothed):
        raise SystemExit(f"yaw smoothing crossed through wrong arithmetic mean: {smoothed}")
    print("audit_fgo_yaw_smoothness_wrap passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
