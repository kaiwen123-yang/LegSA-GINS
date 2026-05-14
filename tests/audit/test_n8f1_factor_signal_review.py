"""Audit test for N8F1 factor signal review.

中文说明：运行 N8F1 factor signal 审计。
"""

import subprocess
import sys


def test_audit_n8f1_factor_signal_review() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8f1_factor_signal_review.py"], check=True)

