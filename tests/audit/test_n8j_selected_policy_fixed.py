"""Audit test for N8J selected policy lock.

中文说明：N8J selected policy 必须与 N8I 一致。
"""

import subprocess
import sys


def test_audit_n8j_selected_policy_fixed():
    subprocess.run([sys.executable, "scripts/audit_n8j_selected_policy_fixed.py"], check=True)
