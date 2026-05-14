"""Audit test for N8C2 residual whitening review.

中文说明：运行 residual whitening 审计入口。
"""

import subprocess
import sys


def test_audit_fgo_residual_whitening_review() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_residual_whitening_review.py"], check=True)
