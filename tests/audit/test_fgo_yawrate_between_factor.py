"""Audit test for N8F yaw-rate between factor.

中文说明：运行 yaw-rate between 审计。
"""

import subprocess
import sys


def test_audit_fgo_yawrate_between_factor() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_yawrate_between_factor.py"], check=True)
