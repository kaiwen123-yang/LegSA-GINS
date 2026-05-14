"""Audit test for N8F relative odometry between factor.

中文说明：运行 relative odometry between 审计。
"""

import subprocess
import sys


def test_audit_fgo_relative_odometry_between_factor() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_relative_odometry_between_factor.py"], check=True)
