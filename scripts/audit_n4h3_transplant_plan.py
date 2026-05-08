#!/usr/bin/env python3
"""Audit N4H3 transplant-plan documentation.

中文说明：只检查 transplant matrix / N4H4 plan 的合同文本，
不实现 EKF、raw Doppler、Go2 prior、LSIM/OIM 或 FGO。
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/experiments/kfgins_full_framework_transplant_matrix.md"
IMPLEMENTATION_PLAN = ROOT / "docs/experiments/n4h4_legsa_v23_core_implementation_plan.md"
INTERFACE_CONTRACT = ROOT / "docs/experiments/n4h4_unified_filter_interface_contract.md"
ROADMAP = ROOT / "docs/experiments/nine_factor_system_roadmap.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    for path in [MATRIX, IMPLEMENTATION_PLAN, INTERFACE_CONTRACT, ROADMAP]:
        if not path.exists():
            raise AssertionError(f"missing {path.relative_to(ROOT)}")
    combined = "\n".join(_read(path) for path in [MATRIX, IMPLEMENTATION_PLAN, INTERFACE_CONTRACT, ROADMAP])
    required = [
        "newImuProcess",
        "isToUpdate",
        "imuInterpolate",
        "imuCompensate",
        "insPropagation",
        "F/G/Phi/Qd",
        "EKFPredict",
        "EKFUpdate",
        "stateFeedback",
        "gnss position/velocity/yaw update",
        "Chinese comments required",
        "no raw Doppler yet",
        "no FGO yet",
        "no performance claim",
    ]
    for item in required:
        if item not in combined:
            raise AssertionError(f"missing transplant-plan string: {item}")
    print("passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
