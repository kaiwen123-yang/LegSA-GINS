"""Audit test for N8I no trace tuning.

中文说明：feedback policy 不能从 trace 调参。
"""

import subprocess
import sys


def test_audit_fgo_feedback_policy_no_trace_tuning():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_policy_no_trace_tuning.py"], check=True)
