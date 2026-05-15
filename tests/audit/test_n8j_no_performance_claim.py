"""Audit test for N8J no performance claim.

中文说明：N8J 是 BY2 工程验证，不做 paper performance claim。
"""

import subprocess
import sys


def test_audit_n8j_no_performance_claim():
    subprocess.run([sys.executable, "scripts/audit_n8j_no_performance_claim.py"], check=True)
