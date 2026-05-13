#!/usr/bin/env python3
"""Audit N8A FGO factor contracts.

中文说明：验证 active/default factor 合同和 Go2 joint factor 状态块边界。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry


def main() -> int:
    registry = build_default_factor_registry()
    required = {
        "ReceiverPositionFactor",
        "ReceiverVelocityFactor",
        "DualYawFactor",
        "RawDopplerVelocityFactor",
        "Go2ProprioceptiveJointFactor",
        "SmoothnessFactor",
    }
    active = set(registry.get("active_default_factors", []))
    if not required.issubset(active):
        raise SystemExit("active factor set incomplete")
    joint = registry.get("go2_joint_factor_contract", {})
    if not joint.get("no_yaw") or not joint.get("no_position") or not joint.get("no_vertical_velocity"):
        raise SystemExit("Go2 joint factor boundary failed")
    print("audit_fgo_factor_contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
