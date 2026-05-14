"""Audit test for N8C2 factor activation review.

中文说明：运行 N8C2 toy 审计入口。
"""

import subprocess
import sys


def test_audit_n8c2_fgo_factor_activation_review() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8c2_fgo_factor_activation_review.py"], check=True)
