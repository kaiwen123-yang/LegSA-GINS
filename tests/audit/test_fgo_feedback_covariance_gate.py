"""中文说明：审计 N8G feedback covariance/gate 保守边界。"""

import subprocess
import sys


def test_fgo_feedback_covariance_gate_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_covariance_gate.py"], check=True)
