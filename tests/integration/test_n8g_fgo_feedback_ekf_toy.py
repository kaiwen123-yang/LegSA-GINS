"""中文说明：N8G toy integration 只验证 feedback EKF 链路，不代表性能。"""

import subprocess
import sys


def test_n8g_fgo_feedback_ekf_toy():
    subprocess.run([sys.executable, "scripts/audit_n8g_fgo_feedback_ekf_foundation.py"], check=True)
