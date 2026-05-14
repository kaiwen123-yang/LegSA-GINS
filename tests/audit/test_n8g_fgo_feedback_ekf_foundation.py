"""中文说明：审计 N8G feedback EKF foundation 的 toy/runtime 边界。"""

import subprocess
import sys


def test_n8g_fgo_feedback_ekf_foundation_audit():
    subprocess.run([sys.executable, "scripts/audit_n8g_fgo_feedback_ekf_foundation.py"], check=True)
