"""Audit test for N8F foot kinematic velocity factor.

中文说明：运行 foot velocity residual/Jacobian 审计。
"""

import subprocess
import sys


def test_audit_fgo_foot_kinematic_velocity_factor() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_foot_kinematic_velocity_factor.py"], check=True)
