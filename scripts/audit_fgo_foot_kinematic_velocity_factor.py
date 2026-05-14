#!/usr/bin/env python3
"""Audit N8F foot kinematic velocity factor.

中文说明：复用 N8F toy 审计检查 foot residual/Jacobian 真实激活。
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py", "--check", "foot"], check=True)
    print("audit_fgo_foot_kinematic_velocity_factor passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
