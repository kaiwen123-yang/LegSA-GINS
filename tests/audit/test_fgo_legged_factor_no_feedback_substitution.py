"""Audit test for N8F no feedback/substitution.

中文说明：运行不反馈 EKF、不替换 NAV 的边界审计。
"""

import subprocess
import sys


def test_audit_fgo_legged_factor_no_feedback_substitution() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_legged_factor_no_feedback_substitution.py"], check=True)
