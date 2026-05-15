"""Audit wrapper for N8H position-disabled boundary.

中文说明：通过脚本审计 primary position disabled 边界。
"""

import subprocess
import sys


def test_fgo_feedback_position_disabled_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_position_disabled.py"], check=True)
