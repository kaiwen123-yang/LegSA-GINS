"""Audit wrapper for N8H gate review.

中文说明：通过脚本审计 gate classification 合法。
"""

import subprocess
import sys


def test_fgo_feedback_gate_reasonable_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_gate_reasonable.py"], check=True)
