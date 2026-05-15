"""Audit test for N8J final validation.

中文说明：toy 审计入口验证 N8J 报告合同。
"""

import subprocess
import sys


def test_audit_n8j_feedback_final_validation():
    subprocess.run([sys.executable, "scripts/audit_n8j_feedback_final_validation.py"], check=True)
