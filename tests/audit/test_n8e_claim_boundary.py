"""Audit test for N8E claim boundary.

中文说明：运行 N8E claim boundary 审计入口。
"""

import subprocess
import sys


def test_audit_n8e_claim_boundary() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8e_claim_boundary.py"], check=True)
