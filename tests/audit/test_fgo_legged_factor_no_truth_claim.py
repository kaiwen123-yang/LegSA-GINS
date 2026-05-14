"""Audit test for N8F no Go2 truth claim.

中文说明：运行 Go2 非真值边界审计。
"""

import subprocess
import sys


def test_audit_fgo_legged_factor_no_truth_claim() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_legged_factor_no_truth_claim.py"], check=True)
