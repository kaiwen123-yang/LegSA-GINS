"""Audit test for N8F legged candidate factor activation.

中文说明：运行 N8F 总体 toy 审计。
"""

import subprocess
import sys


def test_audit_n8f_legged_candidate_factor_activation() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py"], check=True)
