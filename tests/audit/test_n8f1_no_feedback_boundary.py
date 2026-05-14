"""Audit test for N8F1 no-feedback boundary.

中文说明：运行 N8F1 不反馈、不替换边界审计。
"""

import subprocess
import sys


def test_audit_n8f1_no_feedback_boundary() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8f1_no_feedback_boundary.py"], check=True)

