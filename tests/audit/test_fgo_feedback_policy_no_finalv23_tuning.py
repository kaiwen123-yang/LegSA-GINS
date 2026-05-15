"""Audit test for N8I no final_v23 tuning.

中文说明：final_v23 输出不能作为 feedback policy 调参输入。
"""

import subprocess
import sys


def test_audit_fgo_feedback_policy_no_finalv23_tuning():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_policy_no_finalv23_tuning.py"], check=True)
